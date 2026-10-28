"""Engine + catalog tools for the agents (app/tools.py)."""
import copy
import inspect
import logging

import pytest
from fastapi.testclient import TestClient

from app import catalog, sessions
from app import tools as T
from app.main import app
from app.mock_data import ANDREI_PROFILE
from app.schemas import ToolCall
from app.tools import TOOL_SCHEMAS, TOOLS, ToolError, run_tool

client = TestClient(app)


def start_game(horizon: int | None = None) -> str:
    sid = client.post("/api/session").json()["session_id"]
    body = {"session_id": sid}
    if horizon:
        profile = ANDREI_PROFILE.model_dump()
        profile["goal"]["horizon_months"] = horizon
        body["profile"] = profile
    assert client.post("/api/game/start", json=body).status_code == 200
    return sid


def frozen(sid: str) -> tuple:
    s = sessions.get_session(sid)
    return copy.deepcopy((s.sim, s.month, s.year_rep, s.rng.getstate(), s.pending_events, s.log))


# ---------------------------------------------------------------- simulations never mutate the game

def test_simulate_decision_does_not_change_state():
    sid = start_game()
    state_before, raw_before = T.get_state(sid), frozen(sid)
    result = run_tool("simulate_decision", {"ops": {"spend": 2000, "loan": {"name": "X", "principal": 5000, "apr": 0.12, "months": 24}},
                                            "months": 24}, sid)
    assert result["after"]["month"] == 24
    assert T.get_state(sid) == state_before
    assert frozen(sid) == raw_before


def test_compare_scenarios_does_not_change_state_and_includes_baseline():
    sid = start_game()
    before = frozen(sid)
    result = run_tool("compare_scenarios", {"scenarios": {"economisesc": {"emergency_contrib": 500},
                                                          "cheltui mai mult": {"living_add": 300}}, "months": 12}, sid)
    assert [r["scenario"] for r in result["scenarios"]] == ["fără schimbări", "economisesc", "cheltui mai mult"]
    assert result["best"] == "economisesc"
    progress = {r["scenario"]: r["goal_progress"] for r in result["scenarios"]}
    assert progress["economisesc"] > progress["fără schimbări"] > progress["cheltui mai mult"]
    assert frozen(sid) == before


def test_simulation_is_deterministic():
    sid = start_game()
    args = {"ops": {"emergency_contrib": 400, "invest_contrib": 200}, "months": 36}
    assert run_tool("simulate_decision", args, sid) == run_tool("simulate_decision", args, sid)


def test_simulate_decision_by_hand_one_month():
    sid = start_game()
    result = run_tool("simulate_decision", {"ops": {"spend": 1000}, "months": 1}, sid)
    # baseline: 4000 + 4300 - 3770 - 650 = 3880; with the decision 1000 less
    assert result["baseline"]["cash"] == 3880 and result["after"]["cash"] == 2880
    assert result["impact_vs_no_change"]["cash"] == -1000
    assert result["delta"]["cash"] == 2880 - 4000


# ---------------------------------------------------------------- products

def test_loan_cost_by_hand():
    cost = T.loan_cost(10000, 0.12, 36)
    assert cost == {"monthly_payment": 332.14, "total_paid": pytest.approx(11957.15, abs=0.01),
                    "total_interest": pytest.approx(1957.15, abs=0.01)}


def test_compare_products_loan_at_12pct(monkeypatch):
    fake = catalog.Product(id="credit_test", category="credit", name="Credit test", terms="Dobândă fixă de la 12%.",
                           conditions="", best_for="", cautions="")
    monkeypatch.setitem(catalog.PRODUCTS, "credit_test", fake)
    [row] = run_tool("compare_products", {"ids": ["credit_test"], "amount": 10000, "months": 36}, "")["products"]
    assert row["rate"] == 0.12 and row["monthly_payment"] == 332.14
    assert row["total_interest"] == pytest.approx(1957.15, abs=0.01)


def test_compare_products_deposit_net_of_tax():
    # Fresh Money: 6,20% gross; 10.000 lei for 4 months -> 206,67 gross, 20,67 tax, 186,00 net
    [row] = run_tool("compare_products", {"ids": ["fresh_money"], "amount": 10000, "months": 4}, "")["products"]
    assert row["kind"] == "deposit" and row["rate"] == 0.062
    assert (row["gross_interest"], row["tax"], row["net_interest"]) == (206.67, 20.67, 186.0)


def test_compare_products_without_rate_and_unknown_id():
    [row] = run_tool("compare_products", {"ids": ["overdraft"], "amount": 1000, "months": 12}, "")["products"]
    assert row["rate"] is None and "kind" not in row
    with pytest.raises(ToolError):
        run_tool("compare_products", {"ids": ["nu_exista"], "amount": 1000, "months": 12}, "")


def test_search_products_by_category_and_query():
    result = run_tool("search_products", {"category": "economii", "query": "depozit"}, "")
    assert result["products"] and all(p["category"] == "economii" for p in result["products"])
    assert all("depozit" in (p["name"] + p["terms"] + p["best_for"]).lower() for p in result["products"])
    assert run_tool("search_products", {"query": "urgență"}, "")["products"]  # diacritics-insensitive
    with pytest.raises(ToolError):
        run_tool("search_products", {"category": "campanie"}, "")


# ---------------------------------------------------------------- goal and plan

@pytest.mark.parametrize(("horizon", "needed", "on_track_after_1"), [(12, (25000 - 1200) / 12, False), (36, (25000 - 1200) / 36, True)])
def test_goal_progress_12_vs_36_months(horizon, needed, on_track_after_1):
    sid = start_game(horizon)
    g = run_tool("get_goal_progress", {}, sid)
    assert g["months_left"] == horizon and g["monthly_needed"] == pytest.approx(needed, abs=0.01)
    assert g["progress"] == 0.048 and g["remaining"] == 23800
    client.post("/api/game/advance", json={"session_id": sid})
    g = run_tool("get_goal_progress", {}, sid)
    assert g["months_left"] == horizon - 1 and g["on_track"] is on_track_after_1


def test_action_plan_has_3_to_5_actionable_steps():
    sid = start_game(horizon=12)
    client.post("/api/game/advance", json={"session_id": sid})  # behind on a 12-month goal
    steps = run_tool("create_action_plan", {}, sid)["steps"]
    assert 3 <= len(steps) <= 5
    titles = [s["title"] for s in steps]
    assert "Construiește fondul de urgență" in titles and "Pune deoparte automat pentru scop" in titles
    for s in steps:
        assert s["product_id"] is None or catalog.get_product(s["product_id"])
        if s["action"]:  # every suggested action is accepted by the game
            r = client.post("/api/game/action", json={"session_id": sid, "institution": "bank", **s["action"]})
            assert r.status_code == 200, (s, r.json())


def test_action_plan_flags_overdraft_and_expensive_debt():
    sid = start_game()
    sim = sessions.get_session(sid).sim
    sim["overdraft"], sim["cash"] = 2000.0, 500.0
    sim["loans"][0]["apr"] = 0.35
    titles = [s["title"] for s in run_tool("create_action_plan", {}, sid)["steps"]]
    assert titles[0] == "Acoperă descoperitul de cont"
    assert "Echilibrează bugetul lunar" in titles  # Andrei spends 120 lei/month more than he earns
    debt = next(i for i, t in enumerate(titles) if t.startswith("Scapă întâi de"))
    assert debt < titles.index("Construiește fondul de urgență")


# ---------------------------------------------------------------- dispatcher, schemas, logging

def test_every_schema_has_a_matching_function():
    assert [s["name"] for s in TOOL_SCHEMAS] == list(TOOLS)
    for schema in TOOL_SCHEMAS:
        fn, _, needs_session, _ = TOOLS[schema["name"]]
        assert callable(fn) and schema["description"] and schema["input_schema"]["type"] == "object"
        params = [p for p in inspect.signature(fn).parameters if not (needs_session and p == "session_id")]
        assert set(schema["input_schema"].get("properties", {})) == set(params), schema["name"]


@pytest.mark.parametrize(("name", "args"), [
    ("teleport", {}),
    ("simulate_decision", {"ops": {"spend": 100}, "months": 0}),
    ("simulate_decision", {"ops": {"spend": -100}}),           # engine ops validation: no negative spend
    ("simulate_decision", {"ops": {"teleport": 1}}),
    ("simulate_decision", {}),                                  # ops missing
    ("compare_products", {"ids": [], "amount": 100, "months": 12}),
    ("compare_products", {"ids": ["credit_nevoi"], "amount": -5, "months": 12}),
    ("get_state", {"extra": 1}),
])
def test_run_tool_rejects_unknown_tool_and_bad_args(name, args):
    sid = start_game()
    with pytest.raises(ToolError):
        run_tool(name, args, sid)
    entry = sessions.get_session(sid).tool_log[-1]
    assert entry["name"] == name and entry["summary"].startswith("eroare:")


def test_tools_need_a_started_game():
    sid = client.post("/api/session").json()["session_id"]
    with pytest.raises(ToolError, match="nu a pornit"):
        run_tool("get_state", {}, sid)
    with pytest.raises(ToolError, match="inexistentă"):
        run_tool("get_state", {}, "nope")


def test_every_call_is_logged_as_toolcall_without_args_in_server_logs(caplog):
    sid = start_game()
    with caplog.at_level(logging.INFO, logger="extras.tools"):
        run_tool("compare_products", {"ids": ["credit_nevoi"], "amount": 12345, "months": 24}, sid)
    entry = sessions.get_session(sid).tool_log[-1]
    assert set(entry) == {"name", "args", "summary", "duration_ms"} and entry["duration_ms"] >= 0
    assert ToolCall(**entry).args == {"ids": ["credit_nevoi"], "amount": 12345, "months": 24}
    assert "compare_products" in caplog.text and "12345" not in caplog.text


def test_llm_tools_wrap_run_tool():
    sid = start_game()
    wrapped = {t.name: t for t in T.llm_tools(sid)}
    assert set(wrapped) == set(TOOLS)
    assert wrapped["get_goal_progress"].handler()["target_amount"] == 25000
    assert sessions.get_session(sid).tool_log[-1]["name"] == "get_goal_progress"


def test_advisor_returns_real_logged_tool_calls():
    sid = start_game()
    body = client.post("/api/advisor/message", json={"session_id": sid, "text": "Merită un credit?"}).json()
    names = [c["name"] for c in body["tool_calls"]]
    assert names == ["get_goal_progress", "search_products", "compare_products"]
    assert body["tool_calls"] == [{k: v for k, v in c.items() if k != "duration_ms"} for c in sessions.get_session(sid).tool_log[-3:]]
