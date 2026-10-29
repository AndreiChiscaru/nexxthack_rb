"""Choice score stays in 0-100. Agents see the choices and add a bounded note."""
import copy

import pytest
from fastapi.testclient import TestClient

from app.agents import llm
from app.api.business import _tools
from app.main import app
from app.mock_data import ANDREI_PROFILE
from app.sessions import get_session
from app.sim import engine as E
from app.sim import score as player_score
from app.sim.events import EVENT_LIBRARY
from app.sim.score import ScoreError

client = TestClient(app)


def start_game() -> str:
    sid = client.post("/api/session").json()["session_id"]
    assert client.post("/api/game/start", json={"session_id": sid}).status_code == 200
    return sid


def answer(sid: str, event_id: str, option_id: str):
    event = EVENT_LIBRARY[event_id]
    get_session(sid).pending_events = [event.to_api()]
    return client.post("/api/game/action", json={
        "session_id": sid, "institution": event.institution, "action_id": event_id,
        "params": {"option_id": option_id},
    })


def test_a_shorter_goal_moves_more_points_than_a_longer_one():
    def swing(months: int) -> int:
        sid = client.post("/api/session").json()["session_id"]
        profile = ANDREI_PROFILE.model_dump()
        profile["goal"]["horizon_months"] = months
        assert client.post("/api/game/start", json={"session_id": sid, "profile": profile}).status_code == 200
        assert answer(sid, "dentist", "pay_cash").status_code == 200
        choice = get_session(sid).choices[0]
        assert choice["horizon_months"] == months
        return choice["delta"]

    short, medium, long = swing(6), swing(12), swing(36)
    assert short == 16 and medium == 8 and long == 3
    assert short > medium > long
    assert short * 6 >= 80 and long * 36 >= 80


def test_the_risk_answer_moves_the_opening_score_with_the_goal():
    def opened(horizon: int, risk: str, signals: list[str] | None = None) -> int:
        sid = client.post("/api/session").json()["session_id"]
        profile = ANDREI_PROFILE.model_dump()
        profile["goal"]["horizon_months"] = horizon
        profile["risk_tolerance"] = risk
        profile["health"]["insured"] = False
        profile["dependents"] = 0
        profile["source"] = {"statement_uploaded": bool(signals), "statement_score": None, "risk_signals": signals or []}
        assert client.post("/api/game/start", json={"session_id": sid, "profile": profile}).status_code == 200
        return get_session(sid).score_initial

    assert opened(12, "scazuta") > opened(12, "ridicata")
    assert opened(60, "ridicata") > opened(60, "scazuta")
    assert opened(36, "medie", ["Rată la IFN", "Pariuri online"]) < opened(36, "medie")


def test_opening_score_is_the_resilience_and_stays_inside_the_scale():
    sid = start_game()
    session = get_session(sid)
    state = client.get("/api/game/state", params={"session_id": sid}).json()
    base = E.resilience_score(session.sim)
    assert session.score_quiz == player_score.quiz_points(session.profile)
    assert state["score"] == session.score_initial == player_score.clamp(base + session.score_quiz)
    assert session.score_quiz != 0
    assert 0 <= state["score"] <= 100
    assert session.choices == [] and session.score_adjustments == []


def test_the_healthier_option_raises_the_score_and_the_weaker_one_lowers_it():
    cash = answer(start_game(), "dentist", "pay_cash")
    loan = answer(start_game(), "dentist", "installments")
    assert cash.status_code == loan.status_code == 200
    cash_session = get_session(cash.json()["state"]["session_id"])
    loan_session = get_session(loan.json()["state"]["session_id"])
    assert cash_session.choices[0]["delta"] == 3
    assert loan_session.choices[0]["delta"] == -3
    assert cash.json()["state"]["score"] == player_score.clamp(cash_session.score_initial + 3)
    assert loan.json()["state"]["score"] == player_score.clamp(loan_session.score_initial - 3)
    assert cash_session.choices[0]["label"] == "Plătesc din economii"


def test_black_friday_waiting_beats_the_store_card():
    event = EVENT_LIBRARY["black_friday"]
    ops = {option.id: option.ops.to_engine() for option in event.options}
    waiting, _ = player_score.automatic_delta(ops["astept"], list(ops.values()))
    card, _ = player_score.automatic_delta(ops["card_magazin"], list(ops.values()))
    assert waiting == 8 and card == -8


def test_a_single_option_and_a_tie_have_stable_deltas():
    pay, reason = player_score.automatic_delta({"fiscal_pay": 100}, [{"fiscal_pay": 100}])
    assert pay == 6 and "Singura" in reason
    tie, tie_reason = player_score.automatic_delta({"mood": {"stress": 0}}, [{"mood": {"stress": 0}}, {"mood": {"stress": 0}}])
    assert tie == 0 and "echivalente" in tie_reason


def test_saving_adds_points_and_a_pile_of_good_choices_stops_at_100():
    sid = start_game()
    session = get_session(sid)
    moved = client.post("/api/game/action", json={
        "session_id": sid, "institution": "bank", "action_id": "save", "params": {"amount": 100},
    })
    assert moved.status_code == 200
    assert session.choices[-1]["delta"] == 2
    assert moved.json()["state"]["score"] == min(100, session.score_initial + 2)
    session.score_initial = 90
    for _ in range(5):
        player_score.record_free(session, institution="bank", action_id="save", amount=50)
    assert player_score.current(session) == 100


def test_agents_see_the_choice_and_a_second_note_replaces_the_first():
    sid = start_game()
    answer(sid, "dentist", "pay_cash")
    session = get_session(sid)
    choice_id = session.choices[0]["id"]
    before = player_score.current(session)
    first = player_score.add(session, "angel", choice_id, 10, "A plătit fără dobândă.")
    assert first["delta_cerut"] == 10 and first["delta_aplicat"] == 4
    replaced = player_score.add(session, "angel", choice_id, 4, "Corectez: plus mic.")
    assert replaced["scor"] == before + 2
    assert [item["delta"] for item in session.score_adjustments] == [2]
    other = player_score.add(session, "business", choice_id, -3, "Cashul de urgență a scăzut.")
    assert other["scor"] == before + 2 - 1
    assert {item["agent"] for item in session.score_adjustments} == {"angel", "business"}
    view = player_score.public(session)
    assert view["alegeri"][0]["id"] == choice_id
    assert view["valoare"] == other["scor"]
    assert 0 <= view["valoare"] <= 100


def test_additions_are_cut_so_the_score_cannot_leave_0_to_100():
    sid = start_game()
    answer(sid, "dentist", "pay_cash")
    session = get_session(sid)
    choice_id = session.choices[0]["id"]
    session.score_initial = 97
    assert player_score.current(session) == 100  # 97 + 3, the 36-month swing
    topped = player_score.add(session, "angel", choice_id, 10, "Încă un plus.")
    assert topped["scor"] == 100 and topped["delta_aplicat"] == 0
    session.score_adjustments.clear()
    session.score_initial = 3
    session.choices[0]["delta"] = -3
    assert player_score.current(session) == 0
    lifted = player_score.add(session, "investments", choice_id, 10, "Are nevoie de aer.")
    assert lifted["scor"] == 4 and lifted["delta_aplicat"] == 4


@pytest.mark.parametrize(("delta", "reason"), [(11, "prea mult"), (-11, "prea puțin"), (1.5, "fracție"), ("4", "text"), (4, "  ")])
def test_agent_notes_reject_a_delta_outside_the_band_or_an_empty_reason(delta, reason):
    sid = start_game()
    answer(sid, "dentist", "pay_cash")
    session = get_session(sid)
    with pytest.raises(ScoreError):
        player_score.add(session, "angel", session.choices[0]["id"], delta, reason)
    assert session.score_adjustments == []


def test_unknown_choice_and_a_game_that_has_not_started_are_rejected():
    sid = client.post("/api/session").json()["session_id"]
    with pytest.raises(ScoreError, match="nu a pornit"):
        player_score.add(get_session(sid), "angel", "nope", 1, "devreme")
    started = start_game()
    with pytest.raises(ScoreError, match="nu există"):
        player_score.add(get_session(started), "business", "nope", 1, "lipsă")


def test_accountant_and_both_consultants_can_add_and_a_failed_turn_rolls_back():
    sid = start_game()
    answer(sid, "dentist", "installments")
    session = get_session(sid)
    choice_id = session.choices[0]["id"]
    tool = next(item for item in _tools(session) if item.name == "add_to_score")
    result = tool.handler(choice_id=choice_id, delta=-10, reason="Rata adaugă datorie.")
    assert result["scor"] == player_score.clamp(session.score_initial - 3 - 4)
    assert session.tool_log[-1]["name"] == "add_to_score"

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setenv("MOCK_LLM", "false")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-only-placeholder")
        monkeypatch.setattr(llm.anthropic, "Anthropic", lambda: object())
        before_score = player_score.current(session)
        before_notes = copy.deepcopy(session.score_adjustments)

        def failing(_client, system, history, tools, max_tokens):
            assert "add_to_score" in {item.name for item in tools}
            assert choice_id in system and "Plată în rate" in system
            if history[-1]["content"][0]["type"] == "tool_result":
                raise RuntimeError("upstream")
            yield {"type": "_step", "content": [{"type": "tool_use", "id": "score", "name": "add_to_score",
                                                  "input": {"choice_id": choice_id, "delta": 10, "reason": "Revăd."}}],
                   "stop_reason": "tool_use"}

        monkeypatch.setattr(llm, "_stream_step", failing)
        response = client.post("/api/advisor/message", json={"session_id": sid, "text": "Cum a fost alegerea?"})
        assert response.status_code == 502
        assert player_score.current(session) == before_score
        assert session.score_adjustments == before_notes
    finally:
        monkeypatch.undo()
