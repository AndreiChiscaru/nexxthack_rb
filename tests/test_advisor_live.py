import copy
import json

import pytest
from fastapi.testclient import TestClient

from app.agents import llm
from app.main import app
from app.sessions import get_session

client = TestClient(app)


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "false")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-only-placeholder")
    monkeypatch.setattr(llm.anthropic, "Anthropic", lambda: object())


def session(start=True):
    sid = client.post("/api/session").json()["session_id"]
    if start:
        assert client.post("/api/game/start", json={"session_id": sid}).status_code == 200
    return sid


def ask(sid, text):
    return client.post("/api/advisor/message", json={"session_id": sid, "text": text})


def fake_stream(monkeypatch, tool_name="get_state", args=None):
    seen = []

    def step(_client, system, history, tools, max_tokens):
        seen.append((system, copy.deepcopy(history), {tool.name for tool in tools}))
        if history[-1]["content"][0]["type"] == "tool_result":
            content = [{"type": "text", "text": "Răspuns bazat pe unelte."}]
        else:
            content = [{"type": "tool_use", "id": "tool_test", "name": tool_name, "input": args or {}}]
        yield {"type": "_step", "content": content, "stop_reason": "end_turn"}

    monkeypatch.setattr(llm, "_stream_step", step)
    return seen


def test_live_reply_uses_real_readonly_tools_and_retains_tool_history(live, monkeypatch):
    sid = session()
    before = client.get("/api/game/state", params={"session_id": sid}).json()
    seen = fake_stream(monkeypatch, "simulate_decision", {"ops": {"spend": 100}, "months": 12})
    response = ask(sid, "Ce se întâmplă dacă cheltuiesc 100 lei?")
    assert response.status_code == 200
    assert response.json()["reply"] == "Răspuns bazat pe unelte."
    assert response.json()["tool_calls"][0]["name"] == "simulate_decision"
    assert set(response.json()["tool_calls"][0]) == {"name", "args", "summary"}
    assert seen[0][2] == {"get_state", "get_goal_progress", "simulate_decision", "compare_scenarios",
                          "search_products", "compare_products", "create_action_plan"}
    assert any(block["type"] == "tool_result" for turn in get_session(sid).advisor_history for block in turn["content"])
    assert client.get("/api/game/state", params={"session_id": sid}).json() == before


def test_followup_has_full_history_and_fresh_context_isolated_by_session(live, monkeypatch):
    first, second = session(), session()
    seen = fake_stream(monkeypatch)
    assert ask(first, "Ține minte obiectivul meu.").status_code == 200
    client.post("/api/game/advance", json={"session_id": first})
    get_session(first).profile = get_session(first).profile.model_copy(update={"name": "Profil actualizat"})
    assert ask(first, "Și acum?").status_code == 200
    assert '"month": 1' in seen[2][0]
    assert "Profil actualizat" in seen[2][0]
    assert "Ține minte obiectivul meu." in json.dumps(seen[2][1], ensure_ascii=False)
    assert "tool_result" in json.dumps(seen[2][1])
    assert ask(second, "Alt utilizator").status_code == 200
    assert "Ține minte obiectivul meu." not in json.dumps(seen[4][1], ensure_ascii=False)
    assert len(get_session(first).advisor_history) > len(get_session(second).advisor_history)


def test_failed_turn_rolls_back_history_and_tool_log_and_can_retry(live, monkeypatch):
    sid = session()
    fake_stream(monkeypatch)
    assert ask(sid, "Primul mesaj").status_code == 200
    stored = get_session(sid)
    before_history, before_log = copy.deepcopy(stored.advisor_history), copy.deepcopy(stored.tool_log)

    def failing(_client, system, history, tools, max_tokens):
        if history[-1]["content"][0]["type"] == "tool_result":
            raise RuntimeError("private upstream error")
        yield {"type": "_step", "content": [{"type": "tool_use", "id": "fail", "name": "get_state", "input": {}}], "stop_reason": "tool_use"}

    monkeypatch.setattr(llm, "_stream_step", failing)
    response = ask(sid, "Mesaj eșuat")
    assert response.status_code == 502
    assert "private upstream error" not in response.text
    assert stored.advisor_history == before_history
    assert stored.tool_log == before_log
    fake_stream(monkeypatch)
    assert ask(sid, "Reîncearcă").status_code == 200
    assert "Mesaj eșuat" not in json.dumps(stored.advisor_history, ensure_ascii=False)


def test_advisor_before_game_receives_draft_profile(live, monkeypatch):
    sid = session(start=False)
    get_session(sid).agent_profile["data"]["name"] = "Profil în lucru"
    seen = fake_stream(monkeypatch, "search_products", {"category": "economii"})
    assert ask(sid, "Ce pot economisi?").status_code == 200
    assert "Profil în lucru" in seen[0][0]
    assert '"game_state": null' in seen[0][0]


@pytest.mark.parametrize(("key", "mock", "mode"), [("", "false", "mock"), ("test-only", "true", "mock"), ("test-only", "TRUE", "mock"), ("test-only", "false", "live")])
def test_health_reports_same_agent_mode_as_onboarding(monkeypatch, key, mock, mode):
    monkeypatch.setenv("ANTHROPIC_API_KEY", key)
    monkeypatch.setenv("MOCK_LLM", mock)
    assert client.get("/api/health").json()["agent_mode"] == mode


def test_advisor_keeps_onboarding_discussion_without_internal_payloads(live, monkeypatch):
    first, second = session(), session()
    onboarding = get_session(first).onboarding_convo
    onboarding["display"].extend([
        {"role": "user", "text": "Vreau să ajut sora mea să studieze la Viena."},
        {"role": "assistant", "text": "Ținem cont de această prioritate.",
         "tool_calls": [{"name": "update_profile", "args": {"private": "internal-only"}}]},
    ])
    onboarding["history"].append({"role": "user", "content": [{"type": "text", "text": "raw-statement-sentinel"}]})
    before = copy.deepcopy(onboarding)
    seen = fake_stream(monkeypatch)
    assert ask(first, "Ce ți-am spus despre sora mea?").status_code == 200
    assert "Vreau să ajut sora mea să studieze la Viena." in seen[0][0]
    assert "Ținem cont de această prioritate." in seen[0][0]
    assert "raw-statement-sentinel" not in seen[0][0]
    assert "internal-only" not in seen[0][0]
    assert onboarding == before
    assert ask(second, "Ce știi despre mine?").status_code == 200
    assert "Viena" not in seen[2][0]


def test_investments_agent_is_separate_and_uses_the_catalog(live, monkeypatch):
    sid = session(start=False)
    seen = fake_stream(monkeypatch, "search_products", {"category": "investitii"})
    response = client.post("/api/advisor/investments", json={"session_id": sid, "text": "Pot pune bani într-un fond pentru o mașină în 2 ani?"})
    assert response.status_code == 200, response.text
    assert "consultantul de investiții" in seen[0][0]
    stored = get_session(sid)
    assert stored.advisor_history == []
    assert stored.investment_history


def test_investments_agent_mock_names_the_fund(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "true")
    sid = client.post("/api/session").json()["session_id"]
    response = client.post("/api/advisor/investments", json={"session_id": sid, "text": "Vreau să investesc"})
    assert response.status_code == 200, response.text
    assert "fond" in response.json()["reply"].lower()
