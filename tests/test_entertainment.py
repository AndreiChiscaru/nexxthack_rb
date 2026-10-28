from fastapi.testclient import TestClient
from app.main import app
from app.mock_data import ANDREI_PROFILE

client = TestClient(app)

def test_entertainment_preserves_totals_and_routes_cuts():
    profile = ANDREI_PROFILE.model_dump()
    profile["recurring"].update(rent=1000, utilities=200, subscriptions=150, transport=100)
    profile["spending"] = {"food": 500, "leisure": 600}
    profile["categories"] = [
        {"id": "restaurante", "label": "Ieșiri", "institution": "market", "monthly": 400},
        {"id": "livrari", "label": "Livrări", "institution": "market", "monthly": 200},
        {"id": "abonamente", "label": "Streaming", "institution": "home", "monthly": 100},
        {"id": "telefon", "label": "Telefon", "institution": "home", "monthly": 50},
    ]
    sid = client.post("/api/session").json()["session_id"]
    response = client.post("/api/game/start", json={"session_id": sid, "profile": profile})
    assert response.status_code == 200, response.text
    body = response.json()
    state = body["state"]
    expenses = state["monthly"]["expenses"]
    assert expenses.get("entertainment") == 500
    assert expenses["home"] == 1250
    assert expenses["market"] == 800
    assert "entertainment" in [i["id"] for i in state["institutions"]]
    event = body["events"][0]
    assert event["id"] == "taie_restaurante"
    assert event["institution"] == "entertainment"
    before = sum(expenses.values())
    result = client.post("/api/game/action", json={"session_id": sid, "institution": "entertainment", "action_id": event["id"], "params": {"option_id": "taie"}})
    assert result.status_code == 200, result.text
    after = result.json()["state"]["monthly"]["expenses"]
    assert abs(sum(after.values()) - (before - 400)) < 0.02
    assert after["entertainment"] == 100
    assert after["market"] == 800


def test_unitemized_leisure_is_entertainment_but_unknown_subscriptions_stay_home():
    from app.sim.adapter import _base_categories
    profile = ANDREI_PROFILE.model_copy(deep=True)
    profile.categories = []
    profile.spending.leisure = 300
    profile.recurring.subscriptions = 150
    base = _base_categories(profile)
    assert base.get("entertainment") == 300
    assert base["home"] == profile.recurring.rent + profile.recurring.utilities + 150
