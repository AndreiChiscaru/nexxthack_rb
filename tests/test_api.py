import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.mock_data import ANDREI_PROFILE

client = TestClient(app)


def new_session() -> str:
    r = client.post("/api/session")
    assert r.status_code == 200
    return r.json()["session_id"]


@pytest.fixture
def started() -> tuple[str, dict]:
    sid = new_session()
    r = client.post("/api/game/start", json={"session_id": sid})
    assert r.status_code == 200
    return sid, r.json()


def test_create_session():
    sid = new_session()
    assert len(sid) == 32


def test_unknown_session_is_404():
    assert client.get("/api/game/state", params={"session_id": "nope"}).status_code == 404
    assert client.post("/api/onboarding/message", json={"session_id": "nope", "text": "x"}).status_code == 404


def test_state_before_start_is_409():
    assert client.get("/api/game/state", params={"session_id": new_session()}).status_code == 409


def test_onboarding_message_done_after_three():
    sid = new_session()
    bodies = [client.post("/api/onboarding/message", json={"session_id": sid, "text": "salut"}).json()
              for _ in range(3)]
    assert [b["done"] for b in bodies] == [False, False, True]
    assert len(bodies[0]["missing_fields"]) > len(bodies[1]["missing_fields"]) > 0
    assert bodies[2]["missing_fields"] == []
    assert bodies[2]["profile"]["name"] == "Andrei"
    assert bodies[2]["profile"]["income"]["salary"] == 4300


def test_onboarding_statement():
    sid = new_session()
    r = client.post("/api/onboarding/statement", data={"session_id": sid},
                    files={"file": ("extras.pdf", b"%PDF-1.4 fake", "application/pdf")})
    assert r.status_code == 200
    body = r.json()
    assert body["analysis"]["mock"] is True
    assert "income" in body["profile_fields"]
    assert "goal.description" in body["missing_fields"]  # §4.1 paths
    assert "income.salary" not in body["missing_fields"]  # filled from the statement


def test_onboarding_statement_empty_file():
    sid = new_session()
    r = client.post("/api/onboarding/statement", data={"session_id": sid},
                    files={"file": ("extras.pdf", b"", "application/pdf")})
    assert r.status_code == 400


def test_game_start(started):
    _, body = started
    state = body["state"]
    assert state["month"] == 0
    assert state["balance"]["cash"] == 4000
    assert state["balance"]["net_worth"] == 4000 + 1200 - 11000
    assert state["monthly"]["expenses"] == {"home": 1970, "market": 1800, "education": 0,
                                            "health": 0, "business": 0, "bank": 650}
    assert {i["id"] for i in state["institutions"]} == {
        "home", "market", "education", "work", "business", "hospital", "bank"}
    assert len(body["events"]) == 2  # opening events from the scheduler
    pending = {i["id"]: i["pending_events"] for i in state["institutions"]}
    assert sorted(inst for inst, n in pending.items() if n) == sorted(e["institution"] for e in body["events"])
    assert max(pending.values()) == 1


def test_game_state(started):
    sid, body = started
    r = client.get("/api/game/state", params={"session_id": sid})
    assert r.status_code == 200
    assert r.json() == body["state"]


def test_game_action_event_option(started):
    sid, body = started
    event = body["events"][0]
    r = client.post("/api/game/action", json={
        "session_id": sid, "institution": event["institution"], "action_id": event["id"],
        "params": {"option_id": event["options"][0]["id"]}})
    assert r.status_code == 200
    body = r.json()
    assert body["advisor_note"]
    pending = {i["id"]: i["pending_events"] for i in body["state"]["institutions"]}
    assert pending[event["institution"]] == 0


def test_game_action_free_and_invalid(started):
    sid, _ = started
    r = client.post("/api/game/action", json={
        "session_id": sid, "institution": "bank", "action_id": "save", "params": {"amount": 500}})
    assert r.json()["delta"]["savings"] == 500
    bad = client.post("/api/game/action", json={
        "session_id": sid, "institution": "bank", "action_id": "teleport", "params": {}})
    assert bad.status_code == 404  # unknown action_id = unknown event id
    wrong_inst = client.post("/api/game/action", json={
        "session_id": sid, "institution": "nowhere", "action_id": "save", "params": {"amount": 1}})
    assert wrong_inst.status_code == 422


def test_game_advance(started):
    sid, body = started
    r = client.post("/api/game/advance", json={"session_id": sid})
    assert r.status_code == 200
    new = r.json()
    assert new["state"]["month"] == 1
    assert new["state"]["balance"]["cash"] == 4000 + 4300 - (1970 + 1800 + 650)
    assert 0 <= len(new["events"]) <= 2


def test_advisor_message(started):
    sid, _ = started
    r = client.post("/api/advisor/message", json={"session_id": sid, "text": "Merită să iau un credit?"})
    assert r.status_code == 200
    body = r.json()
    assert body["reply"]
    assert 2 <= len(body["tool_calls"]) <= 3
    assert set(body["tool_calls"][0]) == {"name", "args", "summary"}


def test_business_message_with_and_without_file():
    sid = new_session()
    r = client.post("/api/business/message", data={"session_id": sid, "text": "Vreau o cafenea"})
    assert r.status_code == 200
    assert len(r.json()["tool_calls"]) == 2
    r = client.post("/api/business/message", data={"session_id": sid, "text": "Uite planul"},
                    files={"file": ("plan.pdf", b"%PDF fake", "application/pdf")})
    assert r.json()["tool_calls"][0]["name"] == "read_document"


def test_products():
    all_products = client.get("/api/products").json()["products"]
    assert len(all_products) == 23  # data/products.json without the 4 legacy campaign entries
    assert all(p["as_of_date"] and p["disclaimer"] for p in all_products)
    savings = client.get("/api/products", params={"category": "economii"}).json()["products"]
    assert "super_acces_plus" in {p["id"] for p in savings}


@pytest.mark.parametrize(("horizon", "on_track"), [(12, False), (36, True)])
def test_on_track_uses_profile_horizon(horizon, on_track):
    # Savings 1200 / target 25000 = 0.048 progress after month 1: behind 1/12, ahead of 1/36.
    profile = ANDREI_PROFILE.model_dump()
    profile["goal"]["horizon_months"] = horizon
    sid = new_session()
    client.post("/api/game/start", json={"session_id": sid, "profile": profile})
    state = client.post("/api/game/advance", json={"session_id": sid}).json()["state"]
    assert state["goal"]["progress"] == 0.048
    assert state["goal"]["on_track"] is on_track


def test_existing_routes_still_work():
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/").status_code == 200


def test_full_flow():
    sid = new_session()
    for _ in range(3):
        onboarding = client.post("/api/onboarding/message", json={"session_id": sid, "text": "..."}).json()
    assert onboarding["done"]

    started = client.post("/api/game/start", json={"session_id": sid}).json()
    assert started["state"]["session_id"] == sid

    event = started["events"][0]
    acted = client.post("/api/game/action", json={
        "session_id": sid, "institution": event["institution"], "action_id": event["id"],
        "params": {"option_id": event["options"][0]["id"]}})
    assert acted.status_code == 200

    for month in range(1, 4):
        adv = client.post("/api/game/advance", json={"session_id": sid}).json()
        assert adv["state"]["month"] == month

    advice = client.post("/api/advisor/message", json={"session_id": sid, "text": "Ce fac acum?"}).json()
    assert advice["tool_calls"]
    assert client.get("/api/products", params={"category": "investitii"}).json()["products"]

    final = client.get("/api/game/state", params={"session_id": sid}).json()
    assert final["month"] == 3
    assert len(final["log"]) >= 2
