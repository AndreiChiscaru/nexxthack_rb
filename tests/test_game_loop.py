"""Real monthly game loop: engine + adapter behind /api/game/*."""
import pytest
from fastapi.testclient import TestClient

from app import sessions
from app.main import app
from app.mock_data import ANDREI_PROFILE
from app.sim import adapter
from app.sim import engine as E
from app.sim.events import EVENT_LIBRARY

client = TestClient(app)


def start_game(profile: dict | None = None) -> str:
    sid = client.post("/api/session").json()["session_id"]
    body = {"session_id": sid} | ({"profile": profile} if profile else {})
    assert client.post("/api/game/start", json=body).status_code == 200
    return sid


def advance(sid: str) -> dict:
    r = client.post("/api/game/advance", json={"session_id": sid})
    assert r.status_code == 200
    return r.json()


def act(sid: str, action_id: str, amount: float, institution: str = "bank"):
    return client.post("/api/game/action", json={
        "session_id": sid, "institution": institution, "action_id": action_id, "params": {"amount": amount}})


def andrei(**goal) -> dict:
    profile = ANDREI_PROFILE.model_dump()
    profile["goal"].update(goal)
    return profile


# ---------------------------------------------------------------- profile -> engine

def test_profile_to_state_maps_fields():
    sim, _ = adapter.profile_to_state(ANDREI_PROFILE, "seed")
    assert sim["name"] == "Andrei" and sim["age"] == 22
    assert sim["salary"] == 4300 and sim["side_income"] == 0
    assert sim["living"] == 1500 + 350 + 120 + 200 + 1200 + 400
    assert (sim["cash"], sim["emergency"], sim["fund"]) == (4000, 1200, 0)
    [loan] = sim["loans"]
    assert loan["name"] == "Credit nevoi personale"
    assert loan["principal"] == 11000 and loan["apr"] == 0.14
    assert loan["payment"] == 650  # real bank payment kept
    assert loan["months_left"] == E.months_left_for(11000, 0.14, 650) == 19


# ---------------------------------------------------------------- one month, by hand

def test_one_month_by_hand():
    sim, _ = adapter.profile_to_state(ANDREI_PROFILE, "seed")
    adapter.advance_month(sim, 0, adapter.new_year_report(sim))
    # cash = 4000 + 4300 income - 3770 living - 650 loan payment
    assert sim["cash"] == pytest.approx(3880.0)
    # loan: 11000 + 11000 * 0.14 / 12 interest - 650 payment
    assert sim["loans"][0]["principal"] == pytest.approx(11000 + 128.3333 - 650, abs=0.01)
    assert sim["emergency"] == pytest.approx(1200 * (1 + 0.03 / 12))


def test_one_month_via_api_with_delta():
    sid = start_game()
    body = advance(sid)
    state = body["state"]
    assert state["month"] == 1
    assert state["balance"]["cash"] == 3880.0
    assert set(body["delta"]) == {"cash", "savings", "investments", "debt", "net_worth"}
    assert body["delta"]["cash"] == -120.0
    assert body["delta"]["debt"] == pytest.approx(-521.67, abs=0.01)
    assert body["delta"]["savings"] == 3.0
    assert body["delta"]["net_worth"] == pytest.approx(-120 + 3 + 521.67, abs=0.02)
    assert any(e["month"] == 1 and e["text"].startswith("Luna 1:") for e in state["log"])


# ---------------------------------------------------------------- 12 months

def test_twelve_months_age_plus_one_and_debt_down():
    sid = start_game()
    for _ in range(11):
        state = advance(sid)["state"]
    assert state["age"] == 22
    state = advance(sid)["state"]
    assert state["month"] == 12 and state["age"] == 23
    assert state["balance"]["debt"] < 11000
    assert state["monthly"]["income"] == pytest.approx(4300 * 1.04)  # yearly salary growth
    month_lines = [e for e in state["log"] if e["text"].startswith("Luna ")]
    assert len(month_lines) == 12


def test_loan_paid_off_after_its_term():
    sim, _ = adapter.profile_to_state(ANDREI_PROFILE, "seed")
    year_rep = adapter.new_year_report(sim)
    for month in range(19):
        adapter.advance_month(sim, month, year_rep)
    assert sim["loans"] == []
    assert E.total_debt(sim) == 0


def test_yearly_wellbeing_update():
    sim, _ = adapter.profile_to_state(ANDREI_PROFILE, "seed")
    year_rep = adapter.new_year_report(sim)
    stress0 = sim["stress"]
    for month in range(11):
        adapter.advance_month(sim, month, year_rep)
    assert sim["stress"] == stress0  # only changes at the year boundary
    adapter.advance_month(sim, 11, year_rep)
    assert sim["stress"] != stress0
    assert len(sim["history"]) == 2


# ---------------------------------------------------------------- determinism

def test_same_seed_same_simulation():
    runs = []
    for _ in range(2):
        sim, rng = adapter.profile_to_state(ANDREI_PROFILE, "abc123")
        year_rep = adapter.new_year_report(sim)
        for month in range(40):
            adapter.advance_month(sim, month, year_rep)
        runs.append((sim, rng.random()))
    assert runs[0] == runs[1]
    other, _ = adapter.profile_to_state(ANDREI_PROFILE, "other-session")
    assert other["shocks"] != runs[0][0]["shocks"]


def test_same_session_id_same_game(monkeypatch):
    class FixedId:
        hex = "fixed-session-id"

    monkeypatch.setattr(sessions, "uuid4", lambda: FixedId())
    results = []
    for _ in range(2):
        sid = start_game()
        assert sid == "fixed-session-id"
        months = [advance(sid) for _ in range(6)]
        results.append(([m["events"] for m in months], months[-1]["state"]))
    assert results[0] == results[1]


# ---------------------------------------------------------------- expenses mapping

def test_initial_expenses_match_contract_example():
    sid = start_game()
    state = client.get("/api/game/state", params={"session_id": sid}).json()
    assert state["monthly"]["expenses"] == {"home": 1970, "market": 1400, "entertainment": 400, "education": 0,
                                            "health": 0, "business": 0, "bank": 650}


def test_expense_keys_sum_to_engine_outflows():
    sim, _ = adapter.profile_to_state(ANDREI_PROFILE, "seed")
    E.apply_ops(sim, {"insurance_level": 1, "insurance_premium": 90.0, "living_add": 250.0,
                      "loan": {"name": "Rate", "principal": 2400.0, "apr": 0.0, "months": 12}}, [])
    year_rep = adapter.new_year_report(sim)
    for month in range(13):
        adapter.advance_month(sim, month, year_rep)
    ex = adapter.expenses(sim, ANDREI_PROFILE)
    total = sum(ex.model_dump().values())
    assert total == pytest.approx(sim["living"] + sim["insurance_premium"] + E.debt_payments(sim), abs=0.05)
    assert ex.health == 90.0
    # living keeps the profile's home/market proportions after growth
    assert ex.home / ex.market == pytest.approx(1970 / 1400, rel=1e-3)


# ---------------------------------------------------------------- goal

@pytest.mark.parametrize(("horizon", "on_track"), [(12, False), (36, True)])
def test_on_track_against_profile_horizon(horizon, on_track):
    sid = start_game(andrei(horizon_months=horizon))
    goal = advance(sid)["state"]["goal"]
    # (1203 savings + 0 investments) / 25000 = 0.048: behind 1/12, ahead of 1/36
    assert goal["progress"] == 0.048
    assert goal["on_track"] is on_track


def test_goal_progress_counts_investments_and_clamps():
    sim, _ = adapter.profile_to_state(ANDREI_PROFILE, "seed")
    sim["fund"] = 800.0
    assert adapter.goal(sim, ANDREI_PROFILE, 0).progress == pytest.approx(2000 / 25000)
    sim["emergency"] = 100000.0
    assert adapter.goal(sim, ANDREI_PROFILE, 0).progress == 1.0


# ---------------------------------------------------------------- actions

def test_save_500_twice_adds_1000():
    sid = start_game()
    r1, r2 = act(sid, "save", 500), act(sid, "save", 500)
    assert r1.json()["delta"]["savings"] == 500 and r1.json()["delta"]["cash"] == -500
    assert r2.json()["state"]["balance"]["savings"] == 1200 + 1000
    assert r2.json()["state"]["balance"]["cash"] == 4000 - 1000


def test_set_monthly_saving_twice_replaces():
    sid = start_game()
    act(sid, "set_monthly_saving", 300)
    assert act(sid, "set_monthly_saving", 500).status_code == 200
    sim = sessions.get_session(sid).sim
    assert sim["emergency_contrib"] == 500
    state = advance(sid)["state"]
    assert state["balance"]["savings"] == pytest.approx((1200 + 500) * (1 + 0.03 / 12), abs=0.01)


def test_set_monthly_invest_and_stop_with_zero():
    sid = start_game()
    act(sid, "set_monthly_invest", 200)
    # _month adds the contribution first (fund 0 -> 200, cash covers it), then grows the fund by
    # (FUND_APR + shock) / 12. `shock` is the market shock of the current 3-year period, drawn from the
    # rng seeded with session_id (a random uuid here), so read this session's value instead of assuming 0.
    shock = sessions.get_session(sid).sim["shocks"][0]
    expected = 200 * (1 + (E.FUND_APR + shock) / 12)
    assert advance(sid)["state"]["balance"]["investments"] == pytest.approx(expected, abs=0.005)  # API rounds to 2 decimals
    assert act(sid, "set_monthly_invest", 0).status_code == 200
    assert sessions.get_session(sid).sim["invest_contrib"] == 0


def test_invest_one_off():
    sid = start_game()
    body = act(sid, "invest", 1000).json()
    assert body["delta"]["investments"] == 1000 and body["delta"]["cash"] == -1000


def test_repay_prepays_debt():
    sid = start_game()
    body = act(sid, "repay", 2000).json()
    assert body["delta"]["debt"] == -2000 and body["delta"]["cash"] == -2000
    assert body["delta"]["net_worth"] == 0


@pytest.mark.parametrize(("action_id", "amount"), [
    ("save", 0), ("save", -5), ("save", 4000.01), ("invest", 999999), ("repay", 0),
    ("set_monthly_saving", -1), ("set_monthly_invest", 4300.01),
])
def test_invalid_amounts_are_400(action_id, amount):
    sid = start_game()
    assert act(sid, action_id, amount).status_code == 400


def test_event_option_runs_through_engine():
    sid = start_game()
    # Opening events are random per session; make the §4.4 example event the pending one.
    sessions.get_session(sid).pending_events = [EVENT_LIBRARY["dentist"].to_api()]
    body = client.post("/api/game/action", json={
        "session_id": sid, "institution": "hospital", "action_id": "dentist",
        "params": {"option_id": "installments"}}).json()
    assert body["delta"]["debt"] == 1200 and body["delta"]["cash"] == 0
    assert body["state"]["monthly"]["expenses"]["bank"] == pytest.approx(650 + 200)
