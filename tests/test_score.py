"""Choice score stays in 0-100. Agents see the choices and add a bounded note."""
import copy

import pytest
from fastapi.testclient import TestClient

from app.agents import llm
from app.api.business import _tools
from app.main import app
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


def test_opening_score_is_the_resilience_and_stays_inside_the_scale():
    sid = start_game()
    session = get_session(sid)
    state = client.get("/api/game/state", params={"session_id": sid}).json()
    assert state["score"] == E.resilience_score(session.sim) == session.score_initial
    assert 0 <= state["score"] <= 100
    assert session.choices == [] and session.score_adjustments == []


def test_the_healthier_option_raises_the_score_and_the_weaker_one_lowers_it():
    cash = answer(start_game(), "dentist", "pay_cash")
    loan = answer(start_game(), "dentist", "installments")
    assert cash.status_code == loan.status_code == 200
    cash_session = get_session(cash.json()["state"]["session_id"])
    loan_session = get_session(loan.json()["state"]["session_id"])
    assert cash_session.choices[0]["delta"] == 8
    assert loan_session.choices[0]["delta"] == -8
    assert cash.json()["state"]["score"] == player_score.clamp(cash_session.score_initial + 8)
    assert loan.json()["state"]["score"] == player_score.clamp(loan_session.score_initial - 8)
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
    assert session.choices[-1]["delta"] == 5
    assert moved.json()["state"]["score"] == min(100, session.score_initial + 5)
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
    assert first["delta_aplicat"] == 10
    replaced = player_score.add(session, "angel", choice_id, 4, "Corectez: plus mic.")
    assert replaced["scor"] == before + 4
    assert [item["delta"] for item in session.score_adjustments] == [4]
    other = player_score.add(session, "business", choice_id, -3, "Cashul de urgență a scăzut.")
    assert other["scor"] == before + 4 - 3
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
    session.score_initial = 96
    assert player_score.current(session) == 100  # 96 + 8
    topped = player_score.add(session, "angel", choice_id, 10, "Încă un plus.")
    assert topped["scor"] == 100 and topped["delta_aplicat"] == 0
    session.score_adjustments.clear()
    session.score_initial = 3
    session.choices[0]["delta"] = -8
    assert player_score.current(session) == 0
    lifted = player_score.add(session, "investments", choice_id, 10, "Are nevoie de aer.")
    assert lifted["scor"] == 5 and lifted["delta_aplicat"] == 5


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
    assert result["scor"] == player_score.clamp(session.score_initial - 8 - 10)
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
