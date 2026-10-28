from fastapi import APIRouter, HTTPException

from ..mock_data import ANDREI_PROFILE
from ..schemas import (
    Event,
    GameActionRequest,
    GameActionResponse,
    GameAdvanceRequest,
    GameAdvanceResponse,
    GameStartRequest,
    GameStartResponse,
    GameState,
    LogEntry,
)
from ..sessions import Session, game_state, get_session, require_game
from ..sim import adapter
from ..sim import cuts
from ..sim import engine as E
from ..sim import events

router = APIRouter(prefix="/api/game", tags=["game"])

OPENING_EVENTS = 2

# One-off transfers from cash: 400 if amount <= 0 or > cash.
TRANSFER_ACTIONS = {"save", "invest", "repay"}
# Monthly automatic contributions (engine emergency_contrib / invest_contrib, replace the previous value).
# 0 stops the contribution; 400 if < 0 or > monthly income.
MONTHLY_ACTIONS = {"set_monthly_saving": "emergency_contrib", "set_monthly_invest": "invest_contrib"}


def _amount(params: dict) -> float:
    try:
        return float(params.get("amount", 0))
    except (TypeError, ValueError):
        raise HTTPException(400, "params.amount trebuie să fie un număr.")


def _schedule_cut(session: Session) -> list[Event]:
    """One suggestion at a time. A category comes back only after the others, plus a gap."""
    if session.pending_events:
        return []
    track = session.used_events.setdefault("_cuts", {"cycle": [], "last": None, "ready_month": 0})
    if session.month < int(track.get("ready_month") or 0):
        return []
    event = cuts.next_suggestion(session.profile, track["cycle"])
    if event is None:
        if track["cycle"]:
            track["ready_month"] = session.month + cuts.REPEAT_GAP
            track["cycle"] = []
            track["last"] = None
        return []
    track["cycle"].append(event.id.removeprefix("taie_"))
    track["last"] = event.id
    return [event]


def _schedule(session: Session, count: int | None = None) -> list[Event]:
    if session.cut_mode:
        new_events = _schedule_cut(session)
    else:
        picked = events.schedule(session.sim, session.profile, session.month, session.rng,
                                 session.pending_events, session.used_events, count=count)
        new_events = [e.to_api() for e in picked]
    session.pending_events.extend(new_events)
    for e in new_events:
        kind = "Sugestie" if session.cut_mode else "Eveniment nou"
        session.log.append(LogEntry(month=session.month, institution=e.institution, text=f"{kind}: {e.title}"))
    return new_events


@router.post("/start", response_model=GameStartResponse)
def start(req: GameStartRequest):
    session = get_session(req.session_id)
    profile = req.profile or session.profile or ANDREI_PROFILE
    session.profile = profile
    session.sim, session.rng = adapter.profile_to_state(profile, session.id)
    session.month = 0
    session.year_rep = adapter.new_year_report(session.sim)
    session.log = [LogEntry(month=0, institution="home", text=f"{session.sim['name']} începe aventura.")]
    session.pending_events = []
    session.used_events = {}
    session.cut_mode = bool(cuts.eligible(profile))
    opening = _schedule(session, count=1 if session.cut_mode else OPENING_EVENTS)
    return GameStartResponse(state=game_state(session), events=opening)


@router.get("/snapshot", response_model=GameStartResponse)
def snapshot(session_id: str):
    """Recover both authoritative balances and pending decisions after a lost response."""
    session = get_session(session_id)
    return GameStartResponse(state=game_state(session), events=session.pending_events)


@router.get("/state", response_model=GameState)
def state(session_id: str):
    return game_state(get_session(session_id))


def _answer_cut(session: Session, req: GameActionRequest) -> tuple[str, str]:
    pending = next((e for e in session.pending_events if e.id == req.action_id), None)
    if pending is None:
        raise HTTPException(409, f"Sugestia {req.action_id} nu este în așteptare.")
    if req.institution != pending.institution:
        raise HTTPException(400, f"Sugestia {req.action_id} aparține instituției {pending.institution}.")
    option_id = str(req.params.get("option_id", ""))
    if not any(o.id == option_id for o in pending.options):
        raise HTTPException(400, f"option_id invalid; alege din {[o.id for o in pending.options]}.")
    try:
        note = cuts.apply_cut(session.profile, session.sim, req.action_id.removeprefix("taie_"), option_id)
    except ValueError:
        raise HTTPException(400, "Sugestia nu mai corespunde unei cheltuieli din extras.")
    session.pending_events.remove(pending)
    return f"{pending.title}: {option_id}", note


def _answer_event(session: Session, req: GameActionRequest) -> tuple[str, str]:
    """action_id = event id, params.option_id = chosen option. Returns (log text, advisor note)."""
    if req.action_id.startswith("taie_"):
        return _answer_cut(session, req)
    library_event = events.EVENT_LIBRARY.get(req.action_id)
    if library_event is None:
        raise HTTPException(404, f"Eveniment sau acțiune necunoscută: {req.action_id}.")
    pending = next((e for e in session.pending_events if e.id == req.action_id), None)
    if pending is None:
        raise HTTPException(409, f"Evenimentul {req.action_id} nu este în așteptare.")
    if req.institution != library_event.institution:
        raise HTTPException(400, f"Evenimentul {req.action_id} aparține instituției {library_event.institution}.")
    option = library_event.option(str(req.params.get("option_id", "")))
    if option is None:
        raise HTTPException(400, f"option_id invalid; alege din {[o.id for o in library_event.options]}.")

    sim = session.sim
    notes: list[str] = []
    mood = E.apply_ops(sim, option.ops.to_engine(), notes)
    sim["stress"] = max(0.0, min(100.0, float(sim["stress"]) + mood["stress"]))
    sim["confidence"] = max(0.0, min(100.0, float(sim["confidence"]) + mood["confidence"]))
    session.pending_events.remove(pending)
    return f"{library_event.title}: {option.label}", events.advisor_note(option, notes)


@router.post("/action", response_model=GameActionResponse)
def action(req: GameActionRequest):
    session = get_session(req.session_id)
    sim = require_game(session)
    before = adapter.balance(sim)
    notes: list[str] = []
    note: str | None = None

    if req.action_id in TRANSFER_ACTIONS:
        amount = _amount(req.params)
        if amount <= 0 or amount > float(sim["cash"]):
            raise HTTPException(400, f"params.amount trebuie să fie între 0 și numerarul disponibil ({E.money(sim['cash'])}).")
        sim["cash"] = float(sim["cash"]) - amount
        if req.action_id == "save":
            sim["emergency"] = float(sim["emergency"]) + amount
        elif req.action_id == "invest":
            sim["fund"] = float(sim["fund"]) + amount
        else:
            sim["cash"] = float(sim["cash"]) + E.prepay(sim, amount)
        text = f"Acțiune {req.action_id}: {E.money(amount)}"
    elif req.action_id in MONTHLY_ACTIONS:
        amount = _amount(req.params)
        if amount < 0 or amount > E.income(sim):
            raise HTTPException(400, f"params.amount trebuie să fie între 0 și venitul lunar ({E.money(E.income(sim))}).")
        E.apply_ops(sim, {MONTHLY_ACTIONS[req.action_id]: amount}, notes)
        text = f"Acțiune {req.action_id}: {E.money(amount)}/lună"
    else:
        text, note = _answer_event(session, req)

    session.log.append(LogEntry(month=session.month, institution=req.institution, text=text))
    delta = adapter.delta(before, adapter.balance(sim))
    # TODO(real): short note from the advisor agent based on delta + profile.
    note = note or (" ".join(notes) if notes
            else "Bună mișcare, economiile cresc." if delta["savings"] > 0
            else "Atenție: datoria a crescut, verifică dobânda." if delta["debt"] > 0
            else "Am notat decizia ta.")
    return GameActionResponse(state=game_state(session), delta=delta, advisor_note=note)


@router.post("/advance", response_model=GameAdvanceResponse)
def advance(req: GameAdvanceRequest):
    session = get_session(req.session_id)
    sim = require_game(session)
    if session.cut_mode and session.pending_events:
        raise HTTPException(409, "Alege sugestia de reducere înainte să treci la luna următoare.")
    before = adapter.balance(sim)
    summary = adapter.advance_month(sim, session.month, session.year_rep)
    session.month = int(summary["month"])
    session.log.append(LogEntry(
        month=session.month, institution="bank",
        text=f"Luna {session.month}: venit {E.money(summary['income'])}, cheltuieli "
             f"{E.money(summary['expenses'])}, sold {E.money(summary['cash'])}",
    ))
    new_events = _schedule(session)
    return GameAdvanceResponse(state=game_state(session),
                               delta=adapter.delta(before, adapter.balance(sim)), events=new_events)
