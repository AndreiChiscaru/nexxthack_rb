"""Event library (data/events.json): strict validation at import, eligibility and monthly scheduling.

Pure: no FastAPI. Importing this module loads the library, so the app fails fast on bad data.
Ops are validated against exactly what engine.apply_ops understands.
"""
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, model_validator

from ..schemas import Event, EventOption, Institution, Profile
from . import engine as E

EVENTS_PATH = Path(__file__).resolve().parents[2] / "data" / "events.json"
# action_ids handled by /api/game/action itself; an event may not reuse them.
RESERVED_IDS = {"save", "invest", "repay", "set_monthly_saving", "set_monthly_invest"}
MAX_NEW_EVENTS_PER_MONTH = 2


class EventLibraryError(ValueError):
    pass


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoanOp(_Strict):
    name: str | None = None  # engine defaults to "Credit" (§4.4 example omits it)
    principal: float = Field(gt=0)
    apr: float = Field(ge=0, lt=1)
    months: int = Field(gt=0)


class BonusOp(_Strict):
    amount: float = Field(gt=0)
    mode: Literal["prepay", "fund", "safe", "spend"]
    spend: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _spend_matches_mode(self):
        if (self.mode == "spend") != (self.spend is not None):
            raise ValueError("bonus.spend is required for mode 'spend' and allowed only there")
        if self.spend is not None and self.spend > self.amount:
            raise ValueError("bonus.spend cannot exceed bonus.amount")
        return self


class MoodOp(_Strict):
    stress: float = 0
    conf: float = 0


class Ops(_Strict):
    """Exactly the ops engine.apply_ops understands. One-off income goes through `bonus`, never negative `spend`."""
    spend: float | None = Field(default=None, ge=0)
    loan: LoanOp | None = None
    salary_mult: float | None = Field(default=None, gt=0)
    salary_add: float | None = None
    living_add: float | None = None
    side_income_add: float | None = None
    business_value: float | None = None
    car_value: float | None = None
    emergency_contrib: float | None = Field(default=None, ge=0)
    invest_contrib: float | None = Field(default=None, ge=0)
    insurance_level: int | None = Field(default=None, ge=0, le=len(E.INSURANCE_COVERAGE) - 1)
    insurance_premium: float | None = Field(default=None, ge=0)
    medical_cost: float | None = Field(default=None, ge=0)
    finance_months: int | None = Field(default=None, ge=0)
    bonus: BonusOp | None = None
    mood: MoodOp | None = None

    @model_validator(mode="after")
    def _consistent(self):
        if not self.model_dump(exclude_none=True):
            raise ValueError("an option needs at least one op")
        if self.insurance_premium is not None and self.insurance_level is None:
            raise ValueError("insurance_premium needs insurance_level")
        if self.insurance_level is not None and self.insurance_level > 0 and self.insurance_premium is None:
            raise ValueError("insurance_level > 0 needs insurance_premium (engine resets it to 0 otherwise)")
        if self.finance_months is not None and self.medical_cost is None:
            raise ValueError("finance_months needs medical_cost")
        return self

    def to_engine(self) -> dict:
        return self.model_dump(exclude_none=True)


class Conditions(_Strict):
    min_month: int = Field(default=0, ge=0)
    requires_debt: bool = False
    requires_no_insurance: bool = False
    goal_types: list[str] = Field(default_factory=list)


class LibraryOption(_Strict):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    ops: Ops


class LibraryEvent(_Strict):
    id: str = Field(min_length=1)
    institution: Institution
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    options: list[LibraryOption] = Field(min_length=2)
    conditions: Conditions = Field(default_factory=Conditions)
    weight: float = Field(default=1.0, gt=0)

    @model_validator(mode="after")
    def _ids(self):
        if self.id in RESERVED_IDS:
            raise ValueError(f"event id '{self.id}' is reserved for a free action")
        option_ids = [o.id for o in self.options]
        if len(set(option_ids)) != len(option_ids):
            raise ValueError(f"duplicate option ids in event '{self.id}'")
        return self

    def option(self, option_id: str) -> LibraryOption | None:
        return next((o for o in self.options if o.id == option_id), None)

    def to_api(self) -> Event:
        """§4.4 shape only; conditions and weight stay internal."""
        return Event(id=self.id, institution=self.institution, title=self.title, text=self.text,
                     options=[EventOption(id=o.id, label=o.label, ops=o.ops.to_engine()) for o in self.options])


def load_events(path: Path = EVENTS_PATH) -> dict[str, LibraryEvent]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        events = TypeAdapter(list[LibraryEvent]).validate_python(raw)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise EventLibraryError(f"Invalid event library {path}: {exc}") from exc
    library: dict[str, LibraryEvent] = {}
    for event in events:
        if event.id in library:
            raise EventLibraryError(f"Invalid event library {path}: duplicate event id '{event.id}'")
        library[event.id] = event
    return library


EVENT_LIBRARY: dict[str, LibraryEvent] = load_events()


def eligible(event: LibraryEvent, sim: E.SimState, profile: Profile, month: int) -> bool:
    c = event.conditions
    if month < c.min_month:
        return False
    if c.requires_debt and E.total_debt(sim) <= 0.5:
        return False
    if c.requires_no_insurance and int(sim["insurance_level"]) > 0:
        return False
    if c.goal_types and profile.goal.type not in c.goal_types:
        return False
    return True


def schedule(sim: E.SimState, profile: Profile, month: int, rng: random.Random,
             pending: list[Event], used: dict[str, dict], count: int | None = None,
             library: dict[str, LibraryEvent] | None = None) -> list[LibraryEvent]:
    """Picks new events for this month. Mutates `used`: institution -> {"cycle": [ids], "last": id}.

    - 0..MAX_NEW_EVENTS_PER_MONTH events (or exactly `count`, if there are enough candidates),
      weighted by `weight`, drawn from `rng` only, so it's deterministic per session.
    - At most one pending event per institution.
    - Events of an institution come in cycles: none repeats until every currently eligible event of
      that institution was used; then a new cycle starts. The last event of a cycle can't open the next one.
    """
    library = EVENT_LIBRARY if library is None else library
    busy = {e.institution for e in pending}
    by_institution: dict[str, list[LibraryEvent]] = defaultdict(list)
    for event in library.values():
        if eligible(event, sim, profile, month):
            by_institution[event.institution].append(event)

    candidates: list[LibraryEvent] = []
    for institution, events in by_institution.items():
        if institution in busy:
            continue
        track = used.setdefault(institution, {"cycle": [], "last": None})
        if all(e.id in track["cycle"] for e in events):
            track["cycle"] = []
        blocked = set(track["cycle"])
        if len(events) > 1 and track["last"]:
            blocked.add(track["last"])  # no back-to-back repeat across cycles
        candidates.extend(e for e in events if e.id not in blocked)

    k = rng.randint(0, MAX_NEW_EVENTS_PER_MONTH) if count is None else count
    picked: list[LibraryEvent] = []
    while candidates and len(picked) < k:
        event = rng.choices(candidates, weights=[c.weight for c in candidates])[0]
        picked.append(event)
        track = used[event.institution]
        track["cycle"].append(event.id)
        track["last"] = event.id
        candidates = [c for c in candidates if c.institution != event.institution]
    return picked


def advisor_note(option: LibraryOption, notes: list[str]) -> str:
    """Short Romanian explanation of what the chosen option did (no LLM)."""
    ops = option.ops
    parts = list(notes)
    if ops.loan:
        payment = E.pmt(ops.loan.principal, ops.loan.apr, ops.loan.months)
        parts.append(f"Ai luat un credit de {E.money(ops.loan.principal)} la {E.pct(ops.loan.apr)} pe "
                     f"{ops.loan.months} luni: rată de {E.money(payment)}/lună.")
    if ops.spend:
        parts.append(f"Ai plătit {E.money(ops.spend)}: întâi din numerar, apoi din economii.")
    if ops.bonus:
        b = ops.bonus
        parts.append({
            "prepay": f"Ai folosit {E.money(b.amount)} pentru rambursare anticipată.",
            "fund": f"Ai investit {E.money(b.amount)} în fondul diversificat.",
            "safe": f"Ai pus {E.money(b.amount)} deoparte, în fondul de urgență (surplusul merge în depozit).",
            "spend": f"Ai cheltuit {E.money(b.spend or 0)} și ai pus {E.money(b.amount - (b.spend or 0))} deoparte.",
        }[b.mode])
    if ops.salary_mult:
        change = ops.salary_mult - 1
        verb = "crește" if change > 0 else "scade"
        parts.append(f"Salariul {verb} cu {E.pct(abs(change))}; o parte din diferență se reflectă în cheltuieli.")
    if ops.side_income_add:
        parts.append(f"Venit suplimentar de {E.money(ops.side_income_add)}/lună.")
    if ops.living_add:
        verb = "cresc" if ops.living_add > 0 else "scad"
        parts.append(f"Cheltuielile lunare {verb} cu {E.money(abs(ops.living_add))}.")
    if ops.emergency_contrib is not None:
        parts.append(f"De acum pui automat {E.money(ops.emergency_contrib)}/lună în fondul de urgență.")
    if ops.invest_contrib is not None:
        parts.append(f"De acum investești automat {E.money(ops.invest_contrib)}/lună.")
    if ops.insurance_level:
        coverage = E.INSURANCE_COVERAGE[ops.insurance_level]
        parts.append(f"Asigurare activă: {E.money(ops.insurance_premium or 0)}/lună, acoperă ~{coverage:.0%} din costurile medicale.")
    return " ".join(parts[:2]) if parts else "Am notat decizia ta."
