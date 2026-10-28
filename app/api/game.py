from fastapi import APIRouter, HTTPException

from ..mock_data import ANDREI_PROFILE, EVENTS
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
from ..sessions import game_state, get_session, require_game
from ..sim import adapter
from ..sim import engine as E

router = APIRouter(prefix="/api/game", tags=["game"])

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


@router.post("/start", response_model=GameStartResponse)
def start(req: GameStartRequest):
    session = get_session(req.session_id)
    profile = req.profile or session.profile or ANDREI_PROFILE
    session.profile = profile
    session.sim, session.rng = adapter.profile_to_state(profile, session.id)
    session.month = 0
    session.year_rep = adapter.new_year_report(session.sim)
    session.log = [LogEntry(month=0, institution="home", text=f"{session.sim['name']} începe aventura.")]
    # TODO(real): event scheduler picks the opening events from data/events.json.
    session.pending_events = [e for e in EVENTS if e.id in ("dentist", "economisire_automata")]
    return GameStartResponse(state=game_state(session), events=session.pending_events)


@router.get("/state", response_model=GameState)
def state(session_id: str):
    return game_state(get_session(session_id))


@router.post("/action", response_model=GameActionResponse)
def action(req: GameActionRequest):
    session = get_session(req.session_id)
    sim = require_game(session)
    before = adapter.balance(sim)
    notes: list[str] = []

    event = next((e for e in session.pending_events
                  if e.id == req.action_id and e.institution == req.institution), None)
    if event is not None:
        option = next((o for o in event.options if o.id == req.params.get("option_id")), None)
        if option is None:
            raise HTTPException(400, f"option_id invalid; alege din {[o.id for o in event.options]}.")
        mood = E.apply_ops(sim, option.ops, notes)
        sim["stress"] = max(0.0, min(100.0, float(sim["stress"]) + mood["stress"]))
        sim["confidence"] = max(0.0, min(100.0, float(sim["confidence"]) + mood["confidence"]))
        session.pending_events.remove(event)
        text = f"{event.title}: {option.label}"
    elif req.action_id in TRANSFER_ACTIONS:
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
        raise HTTPException(400, f"Acțiune necunoscută: {req.action_id}.")

    session.log.append(LogEntry(month=session.month, institution=req.institution, text=text))
    delta = adapter.delta(before, adapter.balance(sim))
    # TODO(real): short note from the advisor agent based on delta + profile.
    note = (" ".join(notes) if notes
            else "Bună mișcare, economiile cresc." if delta["savings"] > 0
            else "Atenție: datoria a crescut, verifică dobânda." if delta["debt"] > 0
            else "Am notat decizia ta.")
    return GameActionResponse(state=game_state(session), delta=delta, advisor_note=note)


@router.post("/advance", response_model=GameAdvanceResponse)
def advance(req: GameAdvanceRequest):
    session = get_session(req.session_id)
    sim = require_game(session)
    before = adapter.balance(sim)
    summary = adapter.advance_month(sim, session.month, session.year_rep)
    session.month = int(summary["month"])
    session.log.append(LogEntry(
        month=session.month, institution="bank",
        text=f"Luna {session.month}: venit {E.money(summary['income'])}, cheltuieli "
             f"{E.money(summary['expenses'])}, sold {E.money(summary['cash'])}",
    ))

    # TODO(real): event scheduler (task 4); mock picks 0-2 events not already pending, from the session rng.
    pending_ids = {e.id for e in session.pending_events}
    candidates = [e for e in EVENTS if e.id not in pending_ids]
    new_events = session.rng.sample(candidates, k=min(len(candidates), session.rng.randint(0, 2)))
    session.pending_events.extend(new_events)
    for e in new_events:
        session.log.append(LogEntry(month=session.month, institution=e.institution, text=e.title))

    return GameAdvanceResponse(state=game_state(session),
                               delta=adapter.delta(before, adapter.balance(sim)), events=new_events)
