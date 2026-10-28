import random
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.mock_data import ANDREI_PROFILE
from app.sessions import get_session
from app.sim import adapter, engine as E
from app.schemas import Profile, Debt
from app.game_profile import to_game_profile

client = TestClient(app)


def test_deployment_uses_one_worker_for_volatile_sessions():
    service = Path("deploy/extras.service").read_text()
    assert "--workers 1" in service and "--workers 2" not in service


def test_initial_overdraft_is_not_forgiven():
    sim = E.new_state(random.Random(1), {"overdraft": 25000})
    assert sim["overdraft"] == 25000
    assert to_game_profile({"sold_final": -25000})["overdraft"] == 25000


def test_debt_goal_tracks_net_debt_reduction_not_savings():
    profile = ANDREI_PROFILE.model_copy(deep=True)
    profile.goal.type = "achitare_datorii"
    profile.goal.target_amount = 10000
    profile.debts = [Debt(name="Credit", monthly=500, remaining=10000, apr=0)]
    profile = Profile.model_validate(profile.model_dump())
    sim, _ = adapter.profile_to_state(profile, "debt")
    assert adapter.goal(sim, profile, 0).progress == 0
    E.prepay(sim, 2500)
    assert adapter.goal(sim, profile, 1).progress == .25
    E.add_loan(sim, "Nou", 3000, 0, 12)
    assert adapter.goal(sim, profile, 2).progress == 0
    E.prepay(sim, E.total_debt(sim))
    assert adapter.goal(sim, profile, 100).progress == 1
    assert adapter.goal(sim, profile, 100).on_track


def test_debt_goal_explanation_tracks_principal_not_savings():
    sid = client.post("/api/session").json()["session_id"]
    profile = ANDREI_PROFILE.model_dump()
    profile["goal"]["type"] = "achitare_datorii"
    profile["goal"]["target_amount"] = 11000
    started = client.post("/api/game/start", json={"session_id": sid, "profile": profile})
    assert started.status_code == 200, started.text
    from app.tools import run_tool
    progress = run_tool("get_goal_progress", {}, sid)
    assert "achitarea datoriilor" in progress["summary"]
    assert "pus deoparte" not in progress["summary"]
    assert progress["remaining"] == pytest.approx(11000, abs=1)
    assert progress["progress"] == 0


def test_corrected_profile_fields_override_stale_statement_categories():
    sid = client.post("/api/session").json()["session_id"]
    profile = ANDREI_PROFILE.model_dump()
    profile["categories"] = [
        {"id":"uber", "label":"Transport", "institution":"market", "monthly":670},
        {"id":"restaurante", "label":"Restaurante", "institution":"market", "monthly":550},
        {"id":"abonamente", "label":"Abonamente", "institution":"home", "monthly":244},
        {"id":"alimente", "label":"Alimente", "institution":"market", "monthly":100},
    ]
    profile["recurring"].update(transport=120, subscriptions=0)
    profile["spending"].update(food=700, leisure=200)
    result = client.post("/api/game/start", json={"session_id":sid, "profile":profile}).json()
    expenses = result["state"]["monthly"]["expenses"]
    assert expenses["market"] == 820
    assert expenses["entertainment"] == 200
    assert expenses["home"] == profile["recurring"]["rent"] + profile["recurring"]["utilities"]
    categories = {c["id"]:c["monthly"] for c in result["state"]["categories"]}
    assert categories["uber"] == 120 and categories["abonamente"] == 0
    session = get_session(sid)
    assert session.sim["living"] == sum(adapter._base_categories(session.profile).values())


def test_pending_event_snapshot_and_concurrent_answer(monkeypatch):
    import app.api.game as game
    import time
    sid = client.post("/api/session").json()["session_id"]
    started = client.post("/api/game/start", json={"session_id":sid,"profile":ANDREI_PROFILE.model_dump()}).json()
    event = started["events"][0]
    original = game.E.apply_ops
    def slow_apply(*args):
        time.sleep(.05)
        return original(*args)
    monkeypatch.setattr(game.E, "apply_ops", slow_apply)
    gate = Barrier(2)
    def answer():
        gate.wait()
        return client.post("/api/game/action", json={"session_id":sid,"institution":event["institution"],"action_id":event["id"],"params":{"option_id":event["options"][0]["id"]}})
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(lambda _: answer(), range(2)))
    assert sorted(r.status_code for r in replies) == [200,409]
    successful = next(r.json() for r in replies if r.status_code == 200)
    snapshot = client.get("/api/game/snapshot", params={"session_id":sid}).json()
    assert successful["pending_events"] == snapshot["events"]
    step = client.post("/api/game/advance", json={"session_id":sid}).json()
    snapshot = client.get("/api/game/snapshot", params={"session_id":sid}).json()
    assert step["pending_events"] == snapshot["events"]
    assert len({e["id"] for e in step["pending_events"]}) == len(step["pending_events"])


def test_web_engine_debt_goal_also_tracks_repayment():
    from app.demo import engine
    state = engine.new_game({"goal":{"type":"achitare_datorii", "target_amount":10000},
        "bank":{"savings":5000,"debts":[{"name":"Credit","remaining":10000,"monthly_payment":500}]}}, seed=7)
    assert engine.goal_progress(state) == 0
    state["debts"][0]["balance"] = 7500
    assert engine.goal_progress(state) == .25


def test_advisor_debt_goal_uses_repayments_and_partial_target():
    from app.tools import get_goal_progress, create_action_plan
    sid = client.post("/api/session").json()["session_id"]
    profile = ANDREI_PROFILE.model_dump()
    profile["goal"].update(type="achitare_datorii", target_amount=5000)
    profile["debts"] = [{"name":"Credit", "remaining":10000, "monthly":500,"apr":0}]
    client.post("/api/game/start", json={"session_id":sid,"profile":profile})
    session = get_session(sid)
    E.prepay(session.sim,1000)
    session.month = 12
    progress = get_goal_progress(sid)
    assert progress["saved"] == 1000
    assert progress["remaining"] == 4000
    assert progress["progress"] == .2
    plan = str(create_action_plan(sid))
    assert "Pune deoparte automat pentru scop" not in plan
