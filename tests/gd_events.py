"""TEMPORARY test fixture: ids + ops of the 10 decisions in raiffquest/scripts/raiff/events.gd.

Only used to port test_suite.gd's engine tests. The real event library (data/events.json + scheduler)
comes in task 4; delete this file once tests can use it. Text fields (title/scene/lesson) are omitted.
"""
import copy

from app.sim import engine


def _opt(ops: dict) -> dict:
    return {"ops": ops}


def all_events() -> list[dict]:
    return [
        {"id": "buget", "options": [
            _opt({"emergency_contrib": 400.0, "mood": {"stress": -2.0, "conf": 6.0}}),
            _opt({"living_add": 250.0, "mood": {"conf": 0.0}}),
            _opt({"emergency_contrib": 250.0, "invest_contrib": 150.0, "mood": {"conf": 4.0}}),
        ]},
        {"id": "job", "options": [
            _opt({"salary_mult": 1.12, "mood": {"conf": 4.0}}),
            _opt({"salary_mult": 1.35, "living_add": 200.0, "mood": {"stress": 10.0, "conf": 4.0}}),
            _opt({"spend": 2400.0, "salary_mult": 1.22, "mood": {"conf": 8.0}}),
        ]},
        {"id": "auto", "options": [
            _opt({"spend": 10000.0, "loan": {"name": "Credit auto", "principal": 30000.0, "apr": 0.095, "months": 60}, "car_value": 40000.0, "living_add": 450.0, "mood": {"stress": 4.0}}),
            _opt({"spend": 10000.0, "loan": {"name": "Credit auto", "principal": 30000.0, "apr": 0.089, "months": 36}, "car_value": 40000.0, "living_add": 450.0, "mood": {"stress": 6.0}}),
            _opt({"spend": 8000.0, "loan": {"name": "Credit second-hand", "principal": 14000.0, "apr": 0.105, "months": 36}, "car_value": 22000.0, "living_add": 380.0, "mood": {"stress": 2.0}}),
            _opt({"living_add": 250.0, "mood": {"stress": 10.0, "conf": -2.0}}),
        ]},
        {"id": "avarie", "options": [
            _opt({"spend": 9500.0, "mood": {"stress": 4.0}}),
            _opt({"loan": {"name": "Credit nevoi personale", "principal": 9500.0, "apr": 0.139, "months": 24}, "mood": {"stress": 6.0}}),
            _opt({"loan": {"name": "Rate instalator", "principal": 10070.0, "apr": 0.0, "months": 12}, "mood": {"stress": 5.0}}),
            _opt({"spend": 13000.0, "mood": {"stress": 16.0, "conf": -6.0}}),
        ]},
        {"id": "blackfriday", "options": [
            _opt({"spend": 1500.0, "mood": {"conf": 2.0}}),
            _opt({"spend": 7000.0, "mood": {"stress": -5.0, "conf": 2.0}}),
            _opt({"loan": {"name": "Card magazin", "principal": 7000.0, "apr": 0.22, "months": 24}, "mood": {"stress": -2.0, "conf": 1.0}}),
        ]},
        {"id": "asigurari", "options": [
            _opt({"insurance_level": 2, "insurance_premium": 280.0, "mood": {"stress": -6.0, "conf": 4.0}}),
            _opt({"insurance_level": 1, "insurance_premium": 90.0, "mood": {"stress": -2.0}}),
            _opt({"mood": {"conf": 0.0}}),
        ]},
        {"id": "bonus", "options": [
            _opt({"bonus": {"amount": 18000.0, "mode": "prepay"}, "mood": {"stress": -4.0, "conf": 4.0}}),
            _opt({"bonus": {"amount": 18000.0, "mode": "fund"}, "mood": {"conf": 3.0}}),
            _opt({"bonus": {"amount": 18000.0, "mode": "safe"}, "mood": {"stress": -3.0, "conf": 2.0}}),
            _opt({"bonus": {"amount": 18000.0, "mode": "spend", "spend": 12000.0}, "mood": {"stress": -6.0, "conf": 2.0}}),
        ]},
        {"id": "medical", "options": [
            _opt({"medical_cost": 16000.0, "mood": {"stress": 3.0}}),
            _opt({"medical_cost": 7000.0, "mood": {"stress": 14.0, "conf": -4.0}}),
            _opt({"medical_cost": 16000.0, "finance_months": 12, "mood": {"stress": 5.0}}),
        ]},
        {"id": "afacere", "options": [
            _opt({"loan": {"name": "Credit micro-business", "principal": 25000.0, "apr": 0.099, "months": 60}, "business_value": 20000.0, "side_income_add": 1700.0, "mood": {"stress": 10.0, "conf": 6.0}}),
            _opt({"spend": 8000.0, "business_value": 7000.0, "side_income_add": 600.0, "mood": {"stress": 3.0, "conf": 3.0}}),
            _opt({"side_income_add": 500.0, "mood": {"stress": 2.0, "conf": 2.0}}),
            _opt({"mood": {"stress": -2.0}}),
        ]},
        {"id": "pensie", "options": [
            _opt({"invest_contrib": 600.0, "mood": {"conf": 6.0}}),
            _opt({"invest_contrib": 1200.0, "mood": {"stress": 4.0, "conf": 8.0}}),
            _opt({"mood": {"conf": -2.0}}),
        ]},
    ]


def personalize(events: list[dict], s: engine.SimState) -> list[dict]:
    """Ops part of Events.personalize(): adapts the first decision (budget) to the statement figures."""
    out = copy.deepcopy(events)
    budget = out[0]
    surplus = engine.monthly_surplus(s)
    contrib = max(engine.snapped(surplus, 50.0), 100.0)
    to_emergency = max(engine.snapped(contrib * 0.6, 50.0), 50.0)
    to_fund = max(contrib - to_emergency, 50.0)
    budget["options"][0]["ops"]["emergency_contrib"] = contrib
    budget["options"][2]["ops"]["emergency_contrib"] = to_emergency
    budget["options"][2]["ops"]["invest_contrib"] = to_fund
    return out
