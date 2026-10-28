import random
from typing import Any

from fastapi import APIRouter, HTTPException

from ..mock_data import ANDREI_PROFILE, EVENTS, initial_state, recompute
from ..schemas import (
    GameActionRequest,
    GameActionResponse,
    GameAdvanceRequest,
    GameAdvanceResponse,
    GameStartRequest,
    GameStartResponse,
    GameState,
    LogEntry,
)
from ..sessions import Session, get_session, get_state

router = APIRouter(prefix="/api/game", tags=["game"])

# Mock actions available at any time, besides answering a pending event.
FREE_ACTIONS = {"save", "invest", "repay"}


def _snapshot(state: GameState) -> dict[str, float]:
    b = state.balance
    return {"cash": b.cash, "savings": b.savings, "investments": b.investments, "debt": b.debt,
            "net_worth": b.net_worth, "income": state.monthly.income,
            "stress": state.wellbeing.stress, "confidence": state.wellbeing.confidence}


def _sync_pending(session: Session) -> None:
    for inst in session.state.institutions:
        inst.pending_events = sum(1 for e in session.pending_events if e.institution == inst.id)


def _apply_ops(state: GameState, ops: dict[str, Any]) -> None:
    # TODO(real): app/sim/engine.py apply_ops (port of finance_sim.gd), with interest, insurance, etc.
    b = state.balance
    b.cash -= ops.get("spend", 0)
    # A loan finances the purchase directly (events.gd semantics): more debt, no cash in hand.
    if loan := ops.get("loan"):
        b.debt += loan.get("principal", 0)
        if loan.get("months"):
            state.monthly.expenses.bank += round(loan.get("principal", 0) / loan["months"], 2)
    if mult := ops.get("salary_mult"):
        state.monthly.income = round(state.monthly.income * mult, 2)
    state.monthly.expenses.market += ops.get("living_add", 0)
    for key, target in (("emergency_contrib", "savings"), ("invest_contrib", "investments")):
        amount = ops.get(key, 0)
        b.cash -= amount
        setattr(b, target, getattr(b, target) + amount)
    mood = ops.get("mood", {})
    state.wellbeing.stress = max(0, min(100, state.wellbeing.stress + mood.get("stress", 0)))
    state.wellbeing.confidence = max(0, min(100, state.wellbeing.confidence + mood.get("conf", 0)))


@router.post("/start", response_model=GameStartResponse)
def start(req: GameStartRequest):
    session = get_session(req.session_id)
    profile = req.profile or session.profile or ANDREI_PROFILE
    session.profile = profile
    session.state = initial_state(session.id, profile)
    # TODO(real): event scheduler picks the opening events from data/events.json.
    session.pending_events = [e for e in EVENTS if e.id in ("dentist", "economisire_automata")]
    _sync_pending(session)
    return GameStartResponse(state=session.state, events=session.pending_events)


@router.get("/state", response_model=GameState)
def state(session_id: str):
    return get_state(get_session(session_id))


@router.post("/action", response_model=GameActionResponse)
def action(req: GameActionRequest):
    session = get_session(req.session_id)
    state = get_state(session)
    before = _snapshot(state)
    amount = float(req.params.get("amount", 0))

    event = next((e for e in session.pending_events
                  if e.id == req.action_id and e.institution == req.institution), None)
    if event is not None:
        option = next((o for o in event.options if o.id == req.params.get("option_id")), None)
        if option is None:
            raise HTTPException(400, f"option_id invalid; alege din {[o.id for o in event.options]}.")
        _apply_ops(state, option.ops)
        session.pending_events.remove(event)
        text = f"{event.title}: {option.label}"
    elif req.action_id in FREE_ACTIONS:
        if amount <= 0:
            raise HTTPException(400, "params.amount trebuie să fie > 0.")
        if req.action_id == "repay":
            amount = min(amount, state.balance.debt)
            state.balance.cash -= amount
            state.balance.debt -= amount
        else:
            _apply_ops(state, {"emergency_contrib" if req.action_id == "save" else "invest_contrib": amount})
        text = f"Acțiune {req.action_id}: {amount:.0f} lei"
    else:
        raise HTTPException(400, f"Acțiune necunoscută: {req.action_id}.")

    state.log.append(LogEntry(month=state.month, institution=req.institution, text=text))
    recompute(state, session.profile.goal.horizon_months)
    _sync_pending(session)
    after = _snapshot(state)
    delta = {k: round(after[k] - before[k], 2) for k in after if after[k] != before[k]}
    # TODO(real): short note from the advisor agent based on delta + profile.
    note = ("Bună mișcare, fondul de urgență crește." if delta.get("savings", 0) > 0
            else "Atenție: datoria a crescut, verifică dobânda." if delta.get("debt", 0) > 0
            else "Am notat decizia ta.")
    return GameActionResponse(state=state, delta=delta, advisor_note=note)


@router.post("/advance", response_model=GameAdvanceResponse)
def advance(req: GameAdvanceRequest):
    session = get_session(req.session_id)
    state = get_state(session)
    # TODO(real): monthly turn from app/sim/engine.py (interest, auto contributions, per-institution flows).
    expenses = state.monthly.expenses
    total_expenses = (expenses.home + expenses.market + expenses.education
                      + expenses.health + expenses.business + expenses.bank)
    state.month += 1
    if state.month % 12 == 0:
        state.age += 1
    state.balance.cash = round(state.balance.cash + state.monthly.income - total_expenses, 2)
    state.balance.debt = round(max(0.0, state.balance.debt - expenses.bank), 2)

    # TODO(real): event scheduler; mock picks 0-2 events not already pending, deterministic per session+month.
    rng = random.Random(f"{session.id}:{state.month}")
    pending_ids = {e.id for e in session.pending_events}
    candidates = [e for e in EVENTS if e.id not in pending_ids]
    new_events = rng.sample(candidates, k=min(len(candidates), rng.randint(0, 2)))
    session.pending_events.extend(new_events)
    for e in new_events:
        state.log.append(LogEntry(month=state.month, institution=e.institution, text=e.title))

    recompute(state, session.profile.goal.horizon_months)
    _sync_pending(session)
    return GameAdvanceResponse(state=state, events=new_events)
