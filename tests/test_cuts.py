"""Statement averages become cut suggestions on the API the Godot frontend uses."""
from fastapi.testclient import TestClient

from app.main import app
from app.mock_data import ANDREI_PROFILE

client = TestClient(app)


def _total(state: dict) -> float:
    return sum(state["monthly"]["expenses"].values())


def test_sample_statement_reports_category_averages(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "true")
    sid = client.post("/api/session").json()["session_id"]
    response = client.post("/api/onboarding/sample", data={"session_id": sid})
    assert response.status_code == 200, response.text
    categories = {c["id"]: c["monthly"] for c in response.json()["profile_fields"]["categories"]}
    assert categories["uber"] >= 450
    assert categories["restaurante"] >= 400
    assert categories["bursa"] == 800
    assert response.json()["profile_fields"]["recurring"]["rent"] == 0


def test_cuts_replace_surprise_events_and_remove_the_expense():
    sid = client.post("/api/session").json()["session_id"]
    profile = ANDREI_PROFILE.model_dump()
    profile["recurring"]["transport"] = 670
    profile["spending"]["leisure"] = 775
    profile["categories"] = [
        {"id": "uber", "label": "Transport (Uber / Bolt)", "institution": "market", "monthly": 670},
        {"id": "restaurante", "label": "Restaurante și baruri", "institution": "market", "monthly": 550},
        {"id": "pariuri", "label": "Pariuri online", "institution": "market", "monthly": 225},
    ]
    started = client.post("/api/game/start", json={"session_id": sid, "profile": profile})
    assert started.status_code == 200, started.text
    body = started.json()
    assert [e["id"] for e in body["events"]] == ["taie_uber"]
    assert body["state"]["categories"][0]["id"] == "uber"
    before = _total(body["state"])

    chosen = client.post("/api/game/action", json={
        "session_id": sid, "institution": "market", "action_id": "taie_uber", "params": {"option_id": "taie"},
    })
    assert chosen.status_code == 200, chosen.text
    after = chosen.json()["state"]
    assert all(c["id"] != "uber" for c in after["categories"])
    assert abs(_total(after) - (before - 670)) < 1.5
    from app.agents import memory
    assert any("Uber" in note["text"] and note["topic"] == "decizie" for note in memory.load(sid))

    advanced = client.post("/api/game/advance", json={"session_id": sid})
    assert advanced.status_code == 200, advanced.text
    assert [e["id"] for e in advanced.json()["events"]] == ["taie_restaurante"]


def test_a_cut_must_be_answered_and_returns_after_a_gap():
    sid = client.post("/api/session").json()["session_id"]
    profile = ANDREI_PROFILE.model_dump()
    profile["recurring"]["transport"] = 670
    profile["spending"]["leisure"] = 775
    profile["categories"] = [
        {"id": "uber", "label": "Transport (Uber / Bolt)", "institution": "market", "monthly": 670},
    ]
    started = client.post("/api/game/start", json={"session_id": sid, "profile": profile})
    assert [e["id"] for e in started.json()["events"]] == ["taie_uber"]

    blocked = client.post("/api/game/advance", json={"session_id": sid})
    assert blocked.status_code == 409
    assert len(client.get("/api/game/snapshot", params={"session_id": sid}).json()["events"]) == 1

    left = client.post("/api/game/action", json={
        "session_id": sid, "institution": "market", "action_id": "taie_uber", "params": {"option_id": "lasa"},
    })
    assert left.status_code == 200, left.text

    quiet = []
    for _ in range(3):
        step = client.post("/api/game/advance", json={"session_id": sid})
        assert step.status_code == 200, step.text
        quiet.append([e["id"] for e in step.json()["events"]])
    assert quiet == [[], [], []]
    again = client.post("/api/game/advance", json={"session_id": sid})
    assert [e["id"] for e in again.json()["events"]] == ["taie_uber"]
