"""Engine tests: port of raiffquest/test/test_suite.gd (engine parts) + per-op checks.

Scenario tests run on data/events.json (the backend event library).
"""
import math
import random

import pytest

from app.sim import engine as E
from app.sim.events import EVENT_LIBRARY

# Ten decisions from data/events.json mirroring the 10 Godot decisions in events.gd
# (buget, job, auto, avarie, blackfriday, asigurari, bonus, medical, afacere, pensie).
SCENARIO = ["economisire_automata", "promovare", "masina", "avarie_baie", "black_friday",
            "asigurare_sanatate", "bonus_anual", "urgenta_medicala", "cafenea_mobila", "pensie_facultativa"]
# Option ids chosen to match test_suite.gd's strategies option by option:
# PRUDENT [0,2,0,0,0,0,0,0,1,1], CARELESS [1,0,3,0,0,2,2,1,3,2], RECKLESS [1,1,0,3,2,2,3,1,0,2].
PRUDENT = ["500", "accept", "second_hand", "platesc", "astept", "complet", "rambursare", "privat", "economii", "400"]
CARELESS = ["nu_acum", "accept", "transport_comun", "platesc", "cash", "fara", "fond_urgenta", "stat", "refuz", "nu"]
RECKLESS = ["nu_acum", "negociez", "noua", "improvizez", "card_magazin", "fara", "vacanta", "stat", "credit", "nu"]

STATEMENT_PROFILE = {
    "name": "Ion Popescu", "salary": 6850.0, "living": 2320.0, "cash": 5309.81, "overdraft": 0.0,
    "emergency": 0.0, "home_value": 387000.0, "stress": 45.0, "confidence": 55.0,
    "loans": [
        {"name": "Credit ipotecar", "principal": 309828.76, "apr": 0.065, "months": 240},
        {"name": "Credius IFN", "principal": 11107.58, "apr": 0.35, "months": 24},
    ],
}


def state(seed: int = 1, profile: dict | None = None) -> E.SimState:
    return E.new_state(random.Random(seed), profile)


def option(event_id: str, option_id: str) -> dict:
    return {"ops": EVENT_LIBRARY[event_id].option(option_id).ops.to_engine()}


def play(strategy: list[str], seed: int = 1, s: E.SimState | None = None) -> E.SimState:
    """One decision per 36-month period, like the Godot game."""
    s = s if s is not None else state(seed)
    for i, (event_id, option_id) in enumerate(zip(SCENARIO, strategy)):
        E.resolve(s, option(event_id, option_id), s["shocks"][i])
    return s


def blank(**overrides) -> E.SimState:
    """Default state with no randomness side effects, for op-level tests."""
    s = state()
    s.update(overrides)
    return s


# ---------------------------------------------------------------- ported: _test_math

def test_pmt_12000_at_12pct_12_months():
    assert E.pmt(12000.0, 0.12, 12) == pytest.approx(1066.19, abs=0.5)


def test_pmt_zero_apr_is_principal_over_months():
    assert E.pmt(1200.0, 0.0, 12) == pytest.approx(100.0, abs=0.001)


def test_new_state_starts_at_22_with_ten_shocks():
    s = state(7)
    assert s["age"] == 22
    assert len(s["shocks"]) == 10


def test_same_seed_same_shocks():
    assert state(7)["shocks"] == state(7)["shocks"]
    assert state(7)["shocks"] != state(8)["shocks"]


def test_money_format():
    assert "1.234" in E.money(1234.0)
    assert "lei" in E.money(1234.0)


def test_36_month_loan_is_paid_after_one_period():
    s = state(1)
    E.resolve(s, {"ops": {"loan": {"name": "Test", "principal": 10000.0, "apr": 0.1, "months": 36}}}, 0.0)
    assert E.total_debt(s) == pytest.approx(0.0, abs=5.0)


# ---------------------------------------------------------------- ported: _test_every_option_is_finite

@pytest.mark.parametrize("seed", [1, 2, 3])
def test_every_option_is_finite(seed):
    s = state(seed)
    for i, event in enumerate(EVENT_LIBRARY.values()):
        shock = s["shocks"][i % E.PERIODS]
        for opt in event.options:
            rep = E.resolve(E.clone(s), {"ops": opt.ops.to_engine()}, shock)
            nw = rep["after"]["net_worth"]
            assert math.isfinite(nw) and abs(nw) < 100_000_000, f"{event.id} / {opt.id}"
            assert 0.0 <= rep["after"]["stress"] <= 100.0
        if i < E.PERIODS:  # play the first option of the first 10 events in sequence
            E.resolve(s, {"ops": event.options[0].ops.to_engine()}, shock)
    assert math.isfinite(s["overdraft"]) and s["overdraft"] >= 0


# ---------------------------------------------------------------- ported: _test_strategies_differ

def test_strategies_differ_on_most_seeds():
    seeds = range(1, 11)
    results = []
    for seed in seeds:
        p, c, r = play(PRUDENT, seed), play(CARELESS, seed), play(RECKLESS, seed)
        sp, sc, sr = E.resilience_score(p), E.resilience_score(c), E.resilience_score(r)
        results.append((seed, sp, sc, sr))
        assert 0 <= sr and sp <= 100, f"seed {seed}: score out of 0-100"
        assert p["age"] == 52, f"seed {seed}: final age {p['age']}"
        assert E.net_worth(p) > E.net_worth(r), f"seed {seed}: prudent net worth not higher"
        assert E.archetype(sp) != E.archetype(sr), f"seed {seed}: same archetype"
    ordered = [row for row in results if row[1] > row[2] > row[3]]
    assert len(ordered) >= 8, f"prudent > careless > reckless only on {len(ordered)}/10 seeds: {results}"


# ---------------------------------------------------------------- ported: _test_statement_profile (engine parts)

def test_statement_profile_sets_state():
    s = state(5, STATEMENT_PROFILE)
    assert s["from_statement"] and s["name"] == "Ion Popescu"
    assert E.income(s) == pytest.approx(6850.0, abs=0.01)
    assert s["cash"] == pytest.approx(5309.81, abs=0.01)
    assert len(s["loans"]) == 2
    assert E.debt_payments(s) == pytest.approx(2960.0, abs=5.0)
    assert E.net_worth(s) > 0.0, "home value offsets the mortgage"


def test_full_game_on_statement_profile():
    final = play(PRUDENT, s=state(5, STATEMENT_PROFILE))
    assert final["age"] == 52
    assert not math.isnan(E.net_worth(final))


# ---------------------------------------------------------------- ported: engine side of _test_full_playthrough

def test_ten_decisions_end_at_52():
    s = play(PRUDENT)
    assert s["age"] == 52
    assert s["period"] == 10
    assert len(s["history"]) == 1  # new_state seeds history; appending per turn is the caller's job


# ---------------------------------------------------------------- hand-computed sanity checks

def test_pmt_10000_at_12pct_36_months_by_hand():
    # r = 0.01; 10000 * 0.01 / (1 - 1.01^-36) = 100 / 0.301075 = 332.14
    assert E.pmt(10000.0, 0.12, 36) == pytest.approx(332.14, abs=0.01)


def test_one_month_cash_is_cash_plus_income_minus_expenses():
    s = blank(cash=4000.0, salary=4300.0, side_income=0.0, living=3900.0)
    rep = {"interest_paid": 0.0, "overdraft_months": 0, "austerity_months": 0, "invest_gain": 0.0}
    E._month(s, 0.0, rep)
    assert s["cash"] == pytest.approx(4000.0 + 4300.0 - 3900.0)


# ---------------------------------------------------------------- GDScript built-ins

def test_round_half_away_matches_gdscript():
    assert E.round_half_away(2.5) == 3 and round(2.5) == 2
    assert E.round_half_away(-2.5) == -3
    assert E.money(2.5) == "3 lei"


def test_snapped():
    assert E.snapped(0.0137, 0.005) == pytest.approx(0.015)
    assert E.snapped(1234.0, 50.0) == 1250.0


def test_shocks_in_range_and_on_step():
    for shock in state(42)["shocks"]:
        assert -0.06 <= shock <= 0.04
        assert round(shock / 0.005, 6) == pytest.approx(round(shock / 0.005))


def test_signed_money_and_pct():
    assert E.signed_money(0.3) == "0 lei"
    assert E.signed_money(1500.0) == "+1.500 lei"
    assert E.signed_money(-1500.0) == "-1.500 lei"
    assert E.pct(0.139) == "13,9%"


# ---------------------------------------------------------------- derived values

def test_total_debt_investments_net_worth_snapshot():
    s = blank(cash=100.0, emergency=200.0, deposit=300.0, fund=400.0, car_value=500.0,
              business_value=600.0, home_value=700.0, overdraft=50.0)
    E.add_loan(s, "L", 1000.0, 0.1, 12)
    assert E.total_debt(s) == 1050.0
    assert E.investments(s) == 700.0
    assert E.net_worth(s) == 100 + 200 + 700 + 500 + 600 + 700 - 1050
    snap = E.snapshot(s)
    assert set(snap) == {"age", "net_worth", "cash", "emergency", "investments", "debt", "stress", "confidence"}
    assert snap["debt"] == 1050.0


def test_months_left_for():
    assert E.months_left_for(0.0, 0.1, 100.0) == 0
    assert E.months_left_for(1000.0, 0.0, 300.0) == 4
    assert E.months_left_for(10000.0, 0.12, 100.0) == 999  # payment doesn't cover interest
    assert E.months_left_for(10000.0, 0.12, E.pmt(10000.0, 0.12, 36)) == 36


def test_debt_payments_dsr_surplus_emergency():
    s = blank(salary=5000.0, living=3000.0, insurance_premium=100.0, emergency=6000.0)
    E.add_loan(s, "L", 12000.0, 0.0, 12)
    assert E.debt_payments(s) == pytest.approx(1000.0)
    assert E.dsr(s) == pytest.approx(0.2)
    assert E.monthly_surplus(s) == pytest.approx(5000 - 3000 - 1000 - 100)
    assert E.emergency_target(s) == 18000.0
    assert E.emergency_months(s) == pytest.approx(2.0)


# ---------------------------------------------------------------- operations

def test_spend_order_cash_emergency_deposit_overdraft():
    s = blank(cash=100.0, emergency=200.0, deposit=300.0, overdraft=0.0)
    E.spend(s, 1000.0)
    assert (s["cash"], s["emergency"], s["deposit"], s["overdraft"]) == (0.0, 0.0, 0.0, 400.0)


def test_prepay_overdraft_first_then_highest_apr():
    s = blank(overdraft=500.0)
    E.add_loan(s, "cheap", 5000.0, 0.05, 24)
    E.add_loan(s, "pricey", 3000.0, 0.22, 24)
    left = E.prepay(s, 4000.0)
    assert left == 0.0
    assert s["overdraft"] == 0.0
    assert [loan["name"] for loan in s["loans"]] == ["cheap"]  # pricey fully repaid and removed
    assert s["loans"][0]["principal"] == pytest.approx(4500.0)
    assert s["loans"][0]["months_left"] < 24  # payment stays, term shrinks


def test_fill_safe_tops_up_emergency_then_deposit():
    s = blank(living=1000.0, emergency=5000.0, deposit=0.0)
    E.fill_safe(s, 3000.0)
    assert s["emergency"] == 6000.0  # target = 6 * living
    assert s["deposit"] == 2000.0


def test_op_spend_and_loan():
    s = blank(cash=5000.0)
    E.apply_ops(s, {"spend": 1000.0, "loan": {"name": "L", "principal": 10000.0, "apr": 0.12, "months": 36}}, [])
    assert s["cash"] == 4000.0
    assert s["loans"][0]["payment"] == pytest.approx(332.14, abs=0.01)
    assert s["loans"][0]["original"] == 10000.0


def test_op_loan_without_name_defaults():
    s = blank()
    E.apply_ops(s, {"loan": {"principal": 1200.0, "apr": 0.0, "months": 6}}, [])
    assert s["loans"][0]["name"] == "Credit"


def test_op_salary_mult_and_salary_add_have_lifestyle_creep():
    s = blank(salary=4000.0, living=3000.0)
    E.apply_ops(s, {"salary_mult": 1.1}, [])
    assert s["salary"] == pytest.approx(4400.0)
    assert s["living"] == pytest.approx(3000.0 + 400.0 * E.LIFESTYLE_CREEP)
    E.apply_ops(s, {"salary_add": 100.0}, [])
    assert s["salary"] == pytest.approx(4500.0)
    assert s["living"] == pytest.approx(3240.0 + 60.0)


def test_op_living_add_side_income_business_car():
    s = blank(living=3000.0, side_income=0.0, business_value=0.0, car_value=0.0)
    E.apply_ops(s, {"living_add": 200.0, "side_income_add": 1000.0, "business_value": 5000.0, "car_value": 20000.0}, [])
    assert s["living"] == pytest.approx(3000.0 + 200.0 + 300.0)
    assert s["side_income"] == 1000.0
    assert s["business_value"] == 5000.0
    assert s["car_value"] == 20000.0


def test_op_contribs_replace_not_add():
    s = blank(emergency_contrib=400.0, invest_contrib=100.0)
    E.apply_ops(s, {"emergency_contrib": 250.0, "invest_contrib": 150.0}, [])
    assert (s["emergency_contrib"], s["invest_contrib"]) == (250.0, 150.0)


def test_op_insurance_level_and_premium():
    s = blank()
    E.apply_ops(s, {"insurance_level": 2, "insurance_premium": 280.0}, [])
    assert (s["insurance_level"], s["insurance_premium"]) == (2, 280.0)
    E.apply_ops(s, {"insurance_level": 0}, [])
    assert s["insurance_premium"] == 0.0


@pytest.mark.parametrize(("level", "net"), [(0, 16000.0), (1, 10400.0), (2, 2400.0)])
def test_op_medical_cost_with_coverage(level, net):
    s = blank(cash=100000.0, insurance_level=level)
    notes: list[str] = []
    E.apply_ops(s, {"medical_cost": 16000.0}, notes)
    assert s["cash"] == pytest.approx(100000.0 - net)
    assert "Asigurarea a acoperit" in notes[0]


def test_op_medical_cost_financed():
    s = blank(cash=1000.0, insurance_level=0)
    E.apply_ops(s, {"medical_cost": 12000.0, "finance_months": 12}, [])
    assert s["cash"] == 1000.0
    assert s["loans"][0]["name"] == "Plată în rate clinică"
    assert s["loans"][0]["payment"] == pytest.approx(1000.0)


def test_op_bonus_prepay_leftover_goes_safe():
    s = blank(living=1000.0, emergency=0.0, deposit=0.0)
    E.add_loan(s, "L", 5000.0, 0.1, 24)
    notes: list[str] = []
    E.apply_ops(s, {"bonus": {"amount": 18000.0, "mode": "prepay"}}, notes)
    assert s["loans"] == []
    assert s["emergency"] == 6000.0 and s["deposit"] == 7000.0
    assert "După rambursare" in notes[0]


def test_op_bonus_fund_safe_spend():
    s = blank(fund=0.0)
    E.apply_ops(s, {"bonus": {"amount": 18000.0, "mode": "fund"}}, [])
    assert s["fund"] == 18000.0

    s = blank(living=1000.0, emergency=0.0, deposit=0.0)
    E.apply_ops(s, {"bonus": {"amount": 18000.0, "mode": "safe"}}, [])
    assert (s["emergency"], s["deposit"]) == (6000.0, 12000.0)

    s = blank(living=1000.0, emergency=0.0, deposit=0.0)
    E.apply_ops(s, {"bonus": {"amount": 18000.0, "mode": "spend", "spend": 12000.0}}, [])
    assert (s["emergency"], s["deposit"]) == (6000.0, 0.0)


def test_op_mood_is_returned_not_applied():
    s = blank(stress=35.0, confidence=45.0)
    mood = E.apply_ops(s, {"mood": {"stress": 10.0, "conf": -2.0}}, [])
    assert mood == {"stress": 10.0, "confidence": -2.0}
    assert (s["stress"], s["confidence"]) == (35.0, 45.0)


# ---------------------------------------------------------------- simulation

def test_month_overdraft_preserves_debt_above_distress_threshold():
    s = blank(cash=0.0, emergency=0.0, deposit=0.0, overdraft=14900.0, salary=1000.0, living=3000.0)
    rep = {"interest_paid": 0.0, "overdraft_months": 0, "austerity_months": 0, "invest_gain": 0.0}
    E._month(s, 0.0, rep)
    assert s["overdraft"] == pytest.approx(14900 * (1 + E.OVERDRAFT_APR / 12) + 2000)
    assert rep["austerity_months"] == 1 and rep["overdraft_months"] == 1


def test_month_auto_contributions_from_cash():
    s = blank(cash=0.0, salary=5000.0, living=3000.0, emergency=0.0, fund=0.0,
              emergency_contrib=500.0, invest_contrib=300.0)
    E._month(s, 0.0, {"interest_paid": 0.0, "overdraft_months": 0, "austerity_months": 0, "invest_gain": 0.0})
    assert s["cash"] == pytest.approx(2000.0 - 500.0 - 300.0)
    assert s["emergency"] == pytest.approx(500.0 * (1 + E.EMERGENCY_APR / 12))
    assert s["fund"] == pytest.approx(300.0 * (1 + E.FUND_APR / 12))


def test_simulate_period_ages_three_years_and_grows_salary():
    s = blank()
    rep = E.simulate_period(s, 0.0)
    assert s["age"] == 25 and s["period"] == 1
    assert s["salary"] == pytest.approx(4300.0 * 1.04 ** 3)
    assert set(rep) >= {"interest_paid", "overdraft_months", "austerity_months", "invest_gain", "loans_closed", "start", "shock"}


def test_resolve_applies_mood_after_period_and_clamps():
    s = blank()
    rep = E.resolve(s, {"ops": {"mood": {"stress": 500.0}}}, 0.0)
    assert s["stress"] == 100.0
    assert rep["value"] == pytest.approx(E.decision_value(rep))
    assert set(rep) >= {"notes", "before", "after_ops", "after", "net_worth", "monthly_payments",
                        "emergency_months", "overdraft", "value"}


def test_decision_value_formula():
    assert E.decision_value({"after": {"net_worth": 10000.0, "stress": 40.0, "confidence": 50.0}}) == 10000 - 4800 + 3000


def test_resilience_score_and_archetype():
    assert 0 <= E.resilience_score(state()) <= 100
    assert E.archetype(80) == "Arhitectul stabilității"
    assert E.archetype(60) == "Constructor prudent"
    assert E.archetype(40) == "Echilibrist în progres"
    assert E.archetype(39) == "Supraviețuitor de la lună la lună"


def test_retirement_projection():
    s = blank(age=52, deposit=10000.0, fund=0.0, emergency=2000.0, invest_contrib=100.0)
    years = 15
    expected = 11000.0 * 1.06 ** years + 1200.0 * ((1.06 ** years - 1) / 0.06)
    assert E.retirement_projection(s) == pytest.approx(expected)


def test_engine_has_no_io_or_fastapi_imports():
    import inspect
    source = inspect.getsource(E)
    for forbidden in ("fastapi", "open(", "requests", "httpx", "print("):
        assert forbidden not in source
