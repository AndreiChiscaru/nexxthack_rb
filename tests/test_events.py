"""Event library (data/events.json), scheduling and answering events via /api/game/action."""
import inspect
import json
import re
from collections import Counter

import pytest
from fastapi.testclient import TestClient

from app import sessions
from app.api import game as game_routes
from app.main import app
from app.mock_data import ANDREI_PROFILE
from app.schemas import INSTITUTIONS, Event
from app.sim import adapter
from app.sim import engine as E
from app.sim import events as EV
from app.sim.events import EVENT_LIBRARY, EVENTS_PATH, EventLibraryError, Ops

client = TestClient(app)

# Ops read by engine.apply_ops, extracted from its source so the validator can't drift from the engine.
ENGINE_OPS = set(re.findall(r'ops(?:\.has\(|\.get\(|\[)?\s*"(\w+)"', inspect.getsource(E.apply_ops))) | set(
    re.findall(r'"(\w+)" in ops', inspect.getsource(E.apply_ops)))


def start_game(profile: dict | None = None) -> str:
    sid = client.post("/api/session").json()["session_id"]
    body = {"session_id": sid} | ({"profile": profile} if profile else {})
    assert client.post("/api/game/start", json=body).status_code == 200
    return sid


def answer(sid: str, event_id: str, option_id: str, institution: str | None = None):
    institution = institution or EVENT_LIBRARY[event_id].institution
    return client.post("/api/game/action", json={
        "session_id": sid, "institution": institution, "action_id": event_id, "params": {"option_id": option_id}})


def make_pending(sid: str, *event_ids: str) -> None:
    sessions.get_session(sid).pending_events = [EVENT_LIBRARY[i].to_api() for i in event_ids]


# ---------------------------------------------------------------- library

def test_every_institution_has_2_to_4_events():
    counts = Counter(e.institution for e in EVENT_LIBRARY.values())
    assert set(counts) == set(INSTITUTIONS)
    assert all(2 <= n <= 4 for n in counts.values()), counts
    assert 14 <= len(EVENT_LIBRARY) <= 28


def test_event_ids_unique_in_file():
    ids = [e["id"] for e in json.loads(EVENTS_PATH.read_text(encoding="utf-8"))]
    assert len(ids) == len(set(ids))


def test_every_event_validates_as_api_event():
    for event in EVENT_LIBRARY.values():
        api = Event.model_validate(event.to_api().model_dump())
        assert set(api.model_dump()) == {"id", "institution", "title", "text", "options"}  # §4.4 only
        assert len(api.options) >= 2


def test_ops_model_matches_engine_apply_ops():
    assert ENGINE_OPS >= {"spend", "loan", "bonus", "mood", "medical_cost"}  # extraction sanity
    assert set(Ops.model_fields) == ENGINE_OPS


def test_every_op_is_supported_and_applies():
    for event in EVENT_LIBRARY.values():
        for option in event.options:
            ops = option.ops.to_engine()
            assert ops, f"{event.id}/{option.id} has no ops"
            assert set(ops) <= ENGINE_OPS, f"{event.id}/{option.id}: {set(ops) - ENGINE_OPS}"
            sim, _ = adapter.profile_to_state(ANDREI_PROFILE, "x")
            E.apply_ops(sim, ops, [])


def test_no_negative_spend_and_income_labels_say_where_money_goes():
    for event in EVENT_LIBRARY.values():
        for option in event.options:
            ops = option.ops
            assert ops.spend is None or ops.spend >= 0
            if ops.bonus and ops.bonus.mode in ("safe", "fund"):
                assert "fondul" in option.label, f"{event.id}/{option.id}: label should say where the money goes"


def test_reserved_ids_are_the_free_actions():
    assert EV.RESERVED_IDS == set(game_routes.TRANSFER_ACTIONS) | set(game_routes.MONTHLY_ACTIONS)


# ---------------------------------------------------------------- fail fast on bad data

def _write(tmp_path, events):
    path = tmp_path / "events.json"
    path.write_text(json.dumps(events), encoding="utf-8")
    return path


def _event(**overrides):
    event = {"id": "e1", "institution": "home", "title": "T", "text": "X",
             "options": [{"id": "a", "label": "A", "ops": {"spend": 100}},
                         {"id": "b", "label": "B", "ops": {"mood": {"stress": 1}}}]}
    event.update(overrides)
    return event


@pytest.mark.parametrize("events", [
    pytest.param([_event(options=[{"id": "a", "label": "A", "ops": {"teleport": 1}},
                                  {"id": "b", "label": "B", "ops": {"spend": 1}}])], id="unknown-op"),
    pytest.param([_event(options=[{"id": "a", "label": "A", "ops": {"loan": {"principal": 1, "apr": 0, "months": 1, "x": 1}}},
                                  {"id": "b", "label": "B", "ops": {"spend": 1}}])], id="unknown-loan-key"),
    pytest.param([_event(institution="casino")], id="unknown-institution"),
    pytest.param([_event(), _event()], id="duplicate-event-id"),
    pytest.param([_event(options=[{"id": "a", "label": "A"}, {"id": "b", "label": "B", "ops": {"spend": 1}}])], id="option-without-ops"),
    pytest.param([_event(options=[{"id": "a", "label": "A", "ops": {}}, {"id": "b", "label": "B", "ops": {"spend": 1}}])], id="empty-ops"),
    pytest.param([_event(options=[{"id": "a", "label": "A", "ops": {"spend": -900}}, {"id": "b", "label": "B", "ops": {"spend": 1}}])], id="negative-spend"),
    pytest.param([_event(options=[{"id": "a", "label": "A", "ops": {"spend": 1}}, {"id": "a", "label": "B", "ops": {"spend": 1}}])], id="duplicate-option-id"),
    pytest.param([_event(id="save")], id="reserved-id"),
    pytest.param([_event(conditions={"min_level": 3})], id="unknown-condition"),
    pytest.param([_event(options=[{"id": "a", "label": "A", "ops": {"insurance_level": 2}}, {"id": "b", "label": "B", "ops": {"spend": 1}}])], id="insurance-without-premium"),
    pytest.param([_event(options=[{"id": "a", "label": "A", "ops": {"bonus": {"amount": 100, "mode": "spend"}}}, {"id": "b", "label": "B", "ops": {"spend": 1}}])], id="bonus-spend-missing"),
])
def test_invalid_library_fails_fast(tmp_path, events):
    with pytest.raises(EventLibraryError):
        EV.load_events(_write(tmp_path, events))


def test_valid_minimal_library_loads(tmp_path):
    assert list(EV.load_events(_write(tmp_path, [_event()]))) == ["e1"]


# ---------------------------------------------------------------- eligibility

def test_eligible_conditions():
    sim, _ = adapter.profile_to_state(ANDREI_PROFILE, "x")  # has debt, no insurance, goal avans_casa
    lib = EVENT_LIBRARY
    assert not EV.eligible(lib["masina"], sim, ANDREI_PROFILE, 5)  # min_month 6
    assert EV.eligible(lib["masina"], sim, ANDREI_PROFILE, 6)
    assert EV.eligible(lib["cashback_rambursare"], sim, ANDREI_PROFILE, 0)  # requires_debt
    sim_no_debt = E.clone(sim)
    sim_no_debt["loans"] = []
    assert not EV.eligible(lib["cashback_rambursare"], sim_no_debt, ANDREI_PROFILE, 0)
    assert EV.eligible(lib["asigurare_sanatate"], sim, ANDREI_PROFILE, 0)  # requires_no_insurance
    E.apply_ops(sim, {"insurance_level": 1, "insurance_premium": 90}, [])
    assert not EV.eligible(lib["asigurare_sanatate"], sim, ANDREI_PROFILE, 0)
    other_goal = ANDREI_PROFILE.model_copy(deep=True)
    other_goal.goal.type = "vacanta"
    assert EV.eligible(lib["cont_avans"], sim, ANDREI_PROFILE, 0)  # goal_types [avans_casa]
    assert not EV.eligible(lib["cont_avans"], sim, other_goal, 0)


# ---------------------------------------------------------------- scheduling

def _run_schedule(seed: str, months: int, answer_all: bool = True) -> list[list[str]]:
    sim, rng = adapter.profile_to_state(ANDREI_PROFILE, seed)
    pending: list = []
    used: dict[str, dict] = {}
    history = []
    for month in range(months):
        picked = EV.schedule(sim, ANDREI_PROFILE, month, rng, pending, used)
        history.append([e.id for e in picked])
        pending = [] if answer_all else pending + [e.to_api() for e in picked]
    return history


def test_scheduling_deterministic_per_session():
    assert _run_schedule("session-a", 24) == _run_schedule("session-a", 24)


def test_scheduling_differs_across_sessions():
    assert _run_schedule("session-a", 24) != _run_schedule("session-b", 24)


def test_zero_to_two_events_per_month_in_distinct_institutions():
    for picked in _run_schedule("s", 60):
        assert 0 <= len(picked) <= 2
        assert len({EVENT_LIBRARY[i].institution for i in picked}) == len(picked)


def test_no_repeat_until_institution_pool_exhausted():
    # From month 12 on everything except condition-gated events is eligible and stays so (ops aren't applied).
    sim, rng = adapter.profile_to_state(ANDREI_PROFILE, "pool")
    used: dict[str, dict] = {}
    per_institution: dict[str, list[str]] = {i: [] for i in INSTITUTIONS}
    for month in range(12, 12 + 200):
        for event in EV.schedule(sim, ANDREI_PROFILE, month, rng, [], used):
            per_institution[event.institution].append(event.id)
    for institution, seq in per_institution.items():
        pool = {e.id for e in EVENT_LIBRARY.values()
                if e.institution == institution and EV.eligible(e, sim, ANDREI_PROFILE, 12)}
        n = len(pool)
        assert len(seq) >= 3 * n, f"{institution}: too few picks to check cycles"
        # Picks come in cycles of n: each cycle uses every event of the pool exactly once.
        for start in range(0, len(seq) - n + 1, n):
            assert set(seq[start:start + n]) == pool, f"{institution}: cycle {seq[start:start + n]} isn't the full pool"
        assert all(a != b for a, b in zip(seq, seq[1:])), f"{institution}: back-to-back repeat"


def test_max_one_pending_per_institution():
    sim, rng = adapter.profile_to_state(ANDREI_PROFILE, "busy")
    pending = [EVENT_LIBRARY["dentist"].to_api(), EVENT_LIBRARY["promovare"].to_api()]
    for month in range(30):
        for event in EV.schedule(sim, ANDREI_PROFILE, month, rng, pending, {}):
            assert event.institution not in {"hospital", "work"}


def test_pending_never_exceeds_one_per_institution_via_api():
    sid = start_game()
    for _ in range(24):  # never answering
        body = client.post("/api/game/advance", json={"session_id": sid}).json()
        counts = {i["id"]: i["pending_events"] for i in body["state"]["institutions"]}
        assert max(counts.values()) <= 1
        pending = sessions.get_session(sid).pending_events
        assert sum(counts.values()) == len(pending)
        assert {e["id"] for e in body["events"]} <= {e.id for e in pending}


def test_start_schedules_two_month_zero_events():
    for _ in range(10):
        sid = start_game()
        state = client.get("/api/game/state", params={"session_id": sid}).json()
        pending = sessions.get_session(sid).pending_events
        assert len(pending) == 2
        assert all(EVENT_LIBRARY[e.id].conditions.min_month == 0 for e in pending)
        assert sum(i["pending_events"] for i in state["institutions"]) == 2


def test_advance_returns_new_events_as_pending():
    sid = start_game()
    for _ in range(6):
        body = client.post("/api/game/advance", json={"session_id": sid}).json()
        pending_ids = {e.id for e in sessions.get_session(sid).pending_events}
        assert {e["id"] for e in body["events"]} <= pending_ids


# ---------------------------------------------------------------- answering

def test_answer_spend_1200_reduces_cash_by_1200():
    sid = start_game()
    make_pending(sid, "dentist")
    r = answer(sid, "dentist", "pay_cash")
    assert r.status_code == 200
    body = r.json()
    assert body["delta"]["cash"] == -1200
    assert body["delta"]["debt"] == 0
    assert body["state"]["institutions"][INSTITUTIONS.index("hospital")]["pending_events"] == 0
    assert body["state"]["log"][-1]["text"] == "Urgență stomatologică: Plătesc din economii"
    assert "1.200 lei" in body["advisor_note"]


def test_answer_applies_exactly_the_option_ops():
    sid = start_game()
    session = sessions.get_session(sid)
    for event in EVENT_LIBRARY.values():
        for option in event.options:
            expected = E.clone(session.sim)
            mood = E.apply_ops(expected, option.ops.to_engine(), [])
            expected["stress"] = max(0.0, min(100.0, expected["stress"] + mood["stress"]))
            expected["confidence"] = max(0.0, min(100.0, expected["confidence"] + mood["confidence"]))
            make_pending(sid, event.id)
            assert answer(sid, event.id, option.id).status_code == 200, f"{event.id}/{option.id}"
            assert session.sim == expected, f"{event.id}/{option.id}"


def test_answer_loan_note():
    sid = start_game()
    make_pending(sid, "dentist")
    note = answer(sid, "dentist", "installments").json()["advisor_note"]
    assert "credit de 1.200 lei" in note and "200 lei/lună" in note


def test_answer_twice_is_409():
    sid = start_game()
    make_pending(sid, "dentist")
    assert answer(sid, "dentist", "pay_cash").status_code == 200
    r = answer(sid, "dentist", "pay_cash")
    assert r.status_code == 409


def test_known_event_never_scheduled_is_409():
    sid = start_game()
    make_pending(sid)
    assert answer(sid, "masina", "noua").status_code == 409


def test_bad_option_is_400():
    sid = start_game()
    make_pending(sid, "dentist")
    r = answer(sid, "dentist", "nope")
    assert r.status_code == 400
    assert sessions.get_session(sid).pending_events  # still pending


def test_wrong_institution_is_400():
    sid = start_game()
    make_pending(sid, "dentist")
    assert answer(sid, "dentist", "pay_cash", institution="bank").status_code == 400


def test_unknown_event_is_404():
    sid = start_game()
    assert answer(sid, "nu_exista", "a", institution="home").status_code == 404


def test_free_actions_unchanged_with_events_pending():
    sid = start_game()
    make_pending(sid, "dentist")
    r = client.post("/api/game/action", json={
        "session_id": sid, "institution": "bank", "action_id": "save", "params": {"amount": 500}})
    assert r.status_code == 200 and r.json()["delta"]["savings"] == 500
    assert len(sessions.get_session(sid).pending_events) == 1
