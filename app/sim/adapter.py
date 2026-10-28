"""Maps between the §4 API contracts (app/schemas.py) and the engine state (app/sim/engine.py).

Pure functions, no I/O, no FastAPI. The engine dict is the source of truth; GameState is rebuilt from it.
Mapping:
  savings     = emergency + deposit      investments = fund
  debt        = engine.total_debt        net_worth   = engine.net_worth (includes car/home/business)
  goal.progress = saved assets / target, or net debt repaid / repayment target
"""
import random
from typing import Any

from ..schemas import (
    INSTITUTIONS,
    Balance,
    Event,
    GameState,
    GoalProgress,
    InstitutionStatus,
    LogEntry,
    FirmState,
    Monthly,
    MonthlyExpenses,
    ProductHolding,
    Profile,
    Wellbeing,
)
from . import engine as E
from . import firm as F
from .cuts import _bucket

MONTHS_PER_YEAR = 12
DELTA_KEYS = ("cash", "savings", "investments", "debt", "net_worth")


def _r2(x: float) -> float:
    return round(x, 2)


# ---------------------------------------------------------------- profile -> engine

def _expense_total(profile: Profile, obj, attr: str) -> float:
    if attr in obj.model_fields_set:
        return float(getattr(obj, attr))
    rows = [cat for cat in profile.categories
            if (holder := _bucket(profile, cat.id)) and holder[0] is obj and holder[1] == attr]
    return sum(cat.monthly for cat in rows) if rows else float(getattr(obj, attr))


def _base_categories(profile: Profile) -> dict[str, float]:
    """Profile spending grouped by institution; their sum is the engine's `living`."""
    r, s = profile.recurring, profile.spending
    base = {
        "home": r.rent + r.utilities + _expense_total(profile, r, "subscriptions"),
        "market": _expense_total(profile, s, "food") + _expense_total(profile, s, "leisure") + _expense_total(profile, r, "transport"),
        "education": profile.education.tuition_monthly,
        "health": profile.health.monthly_costs,
    }

    # Unknown statement categories have no editable aggregate field.
    for cat in profile.categories:
        if cat.id != "bursa" and _bucket(profile, cat.id) is None:
            bucket = "health" if cat.institution == "hospital" else cat.institution
            base[bucket if bucket in base else "market"] += cat.monthly
    return base


def reconcile_categories(profile: Profile) -> None:
    """Editable totals win; retain each statement category's relative share for cut suggestions."""
    groups = {}
    for cat in profile.categories:
        holder = _bucket(profile, cat.id)
        if holder:
            obj, attr = holder
            groups.setdefault((id(obj), attr), (obj, attr, []))[2].append(cat)
    for obj, attr, rows in groups.values():
        total = sum(cat.monthly for cat in rows)
        target = max(0.0, _expense_total(profile, obj, attr))
        setattr(obj, attr, target)
        if total <= 0:
            continue  # A new aggregate expense is not an identified statement category.
        remaining = round(target, 2)
        for index, cat in enumerate(rows):
            amount = remaining if index == len(rows) - 1 else min(remaining, round(target * cat.monthly / total, 2))
            cat.monthly = amount
            remaining = round(remaining - amount, 2)


def profile_to_state(profile: Profile, seed: str) -> tuple[E.SimState, random.Random]:
    """Builds the engine state from a §4.1 profile. The returned rng is the session's only randomness source."""
    rng = random.Random(seed)
    sim = E.new_state(rng, {
        "name": profile.name or "Jucător",
        "salary": profile.income.salary,
        "living": sum(_base_categories(profile).values()),
        "cash": profile.cash,
        "emergency": profile.savings,
    })
    sim["age"] = profile.age
    # The engine has one extra-income field: other income plus the scholarship.
    sim["side_income"] = float(profile.income.other) + float(profile.education.scholarship)
    sim["fund"] = float(profile.investments)
    for debt in profile.debts:
        months = E.months_left_for(debt.remaining, debt.apr, debt.monthly)
        if debt.remaining <= 0.5 or months <= 0:
            continue
        E.add_loan(sim, debt.name, debt.remaining, debt.apr, months)
        # Keep the real bank payment from the statement instead of the recomputed annuity.
        sim["loans"][-1]["payment"] = float(debt.monthly)
    sim["initial_debt"] = E.total_debt(sim)
    sim["history"] = [E.snapshot(sim)]
    return sim, rng


# ---------------------------------------------------------------- monthly turn

def new_year_report(sim: E.SimState) -> dict[str, Any]:
    """Accumulator that _month fills during a year; closed by advance_month every 12 months."""
    return {"interest_paid": 0.0, "overdraft_months": 0, "austerity_months": 0, "invest_gain": 0.0,
            "start": E.snapshot(sim)}


def advance_month(sim: E.SimState, month: int, year_rep: dict[str, Any]) -> dict[str, float]:
    """Runs one month. `month` = months already elapsed. Mutates `sim` and `year_rep`.

    Every 12 months applies the same yearly updates as engine.simulate_period (salary growth,
    inflation, car depreciation), age +1 and wellbeing; then restarts `year_rep`.
    """
    shock = sim["shocks"][min(month // E.MONTHS_PER_PERIOD, E.PERIODS - 1)]
    # Firm cash is personal money for this month only. It must not stick to side_income and grow with it.
    firm_cash = F.month_cash(sim)
    if firm_cash:
        sim["side_income"] = float(sim["side_income"]) + firm_cash
    inc = E.income(sim)
    out = float(sim["living"]) + float(sim["insurance_premium"]) + E.debt_payments(sim)
    try:
        E._month(sim, shock, year_rep)
    finally:
        if firm_cash:
            sim["side_income"] = float(sim["side_income"]) - firm_cash
    F.accrue(sim)
    month += 1
    if month % MONTHS_PER_YEAR == 0:
        sim["salary"] = float(sim["salary"]) * (1.0 + E.SALARY_GROWTH)
        sim["living"] = float(sim["living"]) * (1.0 + E.LIVING_INFLATION)
        sim["side_income"] = float(sim["side_income"]) * 1.03
        sim["car_value"] = float(sim["car_value"]) * (1.0 - E.CAR_DEPRECIATION)
        sim["age"] = int(sim["age"]) + 1
        sim["interest_paid_total"] = float(sim["interest_paid_total"]) + float(year_rep["interest_paid"])
        E._update_wellbeing(sim, year_rep)
        sim["history"].append(E.snapshot(sim))
        year_rep.clear()
        year_rep.update(new_year_report(sim))
    sim["period"] = month // E.MONTHS_PER_PERIOD
    return {"month": month, "income": inc, "expenses": out, "cash": float(sim["cash"])}


# ---------------------------------------------------------------- engine -> GameState

def expenses(sim: E.SimState, profile: Profile) -> MonthlyExpenses:
    """The single mapping of engine outflows onto §4.2 expense keys.

    `living` is split across home/market/education/health by the profile's starting proportions, so those
    keys sum to living + insurance_premium + debt_payments (what _month subtracts).
    health = its share of living (profile health.monthly_costs) + the insurance premium.
    business is the firm's operating cost when the accountant has started one; it is not part of `living`.
    """
    base = _base_categories(profile)
    total = sum(base.values())
    shares = ({k: v / total for k, v in base.items()} if total > 0
              else {"home": 0.0, "market": 1.0, "education": 0.0, "health": 0.0})
    living = float(sim["living"])
    running = sim.get("firm") if isinstance(sim.get("firm"), dict) and not sim["firm"].get("_projection") else None
    return MonthlyExpenses(
        home=_r2(living * shares["home"]),
        market=_r2(living * shares["market"]),
        education=_r2(living * shares["education"]),
        health=_r2(living * shares["health"] + float(sim["insurance_premium"])),
        business=_r2(float(running["monthly_expenses"])) if running else 0.0,
        bank=_r2(E.debt_payments(sim)),
    )


def _shown_income(sim: E.SimState) -> float:
    running = sim.get("firm") if isinstance(sim.get("firm"), dict) and not sim["firm"].get("_projection") else None
    extra = float(running["monthly_revenue"]) if running else 0.0
    return E.income(sim) + extra


def _firm_state(sim: E.SimState, month: int, pending_events: list[Event]) -> FirmState | None:
    view = F.public_view(sim, month)
    if not view:
        return None
    # The deadline event holds the amount after it is taken off the accrual, until the player pays.
    for event in pending_events:
        if event.id.startswith("fiscal_"):
            pay = next((option.ops.get("fiscal_pay") for option in event.options if option.id == "plateste"), None)
            if pay:
                view["taxes_due"] = round(float(view["taxes_due"]) + float(pay), 2)
    return FirmState(**view)


def balance(sim: E.SimState) -> Balance:
    return Balance(
        cash=_r2(float(sim["cash"])),
        savings=_r2(float(sim["emergency"]) + float(sim["deposit"])),
        investments=_r2(float(sim["fund"])),
        debt=_r2(E.total_debt(sim)),
        net_worth=_r2(E.net_worth(sim)),
    )


def delta(before: Balance, after: Balance) -> dict[str, float]:
    return {k: _r2(getattr(after, k) - getattr(before, k)) for k in DELTA_KEYS}


def goal(sim: E.SimState, profile: Profile, month: int) -> GoalProgress:
    b = balance(sim)
    target = profile.goal.target_amount
    if profile.goal.type == "achitare_datorii":
        initial = float(sim.get("initial_debt", sum(d.remaining for d in profile.debts)))
        repayment_target = min(initial, target) if target > 0 else initial
        progress = min(1.0, max(0.0, (initial - b.debt) / repayment_target)) if repayment_target > 0 else float(b.debt <= 0)
    else:
        progress = min(1.0, max(0.0, (b.savings + b.investments) / target)) if target > 0 else 1.0
    return GoalProgress(
        type=profile.goal.type,
        target_amount=target,
        progress=round(progress, 3),
        on_track=progress >= min(1.0, month / max(1, profile.goal.horizon_months)),
    )


# Engine balance -> the catalog product (data/products.json) it represents in GameState.products.
HOLDING_PRODUCTS = {"emergency": "super_acces_plus", "deposit": "depozit_1_an", "fund": "fonduri_smartinvest"}


def products(sim: E.SimState) -> list[ProductHolding]:
    return [ProductHolding(id=pid, balance=_r2(float(sim[key])))
            for key, pid in HOLDING_PRODUCTS.items() if float(sim[key]) > 0.5]


def to_game_state(session_id: str, sim: E.SimState, profile: Profile, month: int,
                  pending_events: list[Event], log: list[LogEntry], score: int = 0) -> GameState:
    return GameState(
        session_id=session_id,
        month=month,
        age=int(sim["age"]),
        goal=goal(sim, profile, month),
        balance=balance(sim),
        monthly=Monthly(income=_r2(_shown_income(sim)), expenses=expenses(sim, profile)),
        wellbeing=Wellbeing(stress=_r2(float(sim["stress"])), confidence=_r2(float(sim["confidence"]))),
        institutions=[InstitutionStatus(id=i, pending_events=sum(1 for e in pending_events if e.institution == i))
                      for i in INSTITUTIONS],
        products=products(sim),
        log=list(log),
        categories=list(profile.categories),
        firm=_firm_state(sim, month, pending_events),
        score=max(0, min(100, int(score))),
    )
