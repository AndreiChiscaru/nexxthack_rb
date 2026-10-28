"""The fictional student statement: 12 months, category averages, habit events instead of rent and appliances."""
import importlib.util
from pathlib import Path

from app.agents import onboarding
from app.demo import engine
from app.statement_spend import summarize

ROOT = Path(__file__).resolve().parents[1]


def _statement_text() -> str:
    path = ROOT / "deploy" / "make_student_statement.py"
    spec = importlib.util.spec_from_file_location("make_student_statement", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    text, _balance = module.build()
    return text


def test_student_statement_averages_twelve_months():
    stats = summarize(_statement_text())
    assert stats["luni"] == 12
    assert stats["titular"] == "MATEI POP"
    assert stats["varsta"] == 21
    assert stats["locuinta"] == "parinti"
    by_id = {c["id"]: c["medie_lunara"] for c in stats["categorii"]}
    assert by_id["uber"] >= 450
    assert by_id["restaurante"] >= 400
    assert by_id["uber"] > by_id["alimente"]
    assert by_id["restaurante"] > by_id["alimente"]
    assert by_id["pariuri"] >= 80
    assert by_id["rate"] >= 80
    assert stats["cheltuieli_medii"] > stats["venit_mediu"] + stats["alte_intrari_medii"]
    assert by_id["uber"] + by_id["restaurante"] > stats["venit_mediu"] * 0.5
    assert "chirie" not in {c["id"] for c in stats["categorii"]}


def test_habit_events_replace_rent_and_appliances():
    stats = summarize(_statement_text())
    profile = {
        "name": "Matei Pop",
        "age": 21,
        "income": {"salary": stats["venit_mediu"], "other": stats["alte_intrari_medii"]},
        "home": {"housing": 0, "utilities": 0},
        "education": {"status": "student"},
        "bank": {"cash": stats["sold_final"], "savings": 0},
        "categories": [{"id": c["id"], "label": c["label"], "institution": c["institution"], "monthly": c["medie_lunara"]}
                       for c in stats["categorii"]],
        "statement_months": 12,
        "goal": {"description": "Fond de urgență", "target_amount": 5000, "horizon_months": 12},
    }
    state = engine.new_game(profile, seed=7)
    assert state["from_statement"] and state["lives_with_parents"] and state["statement_months"] == 12
    labels = [row["label"] for row in engine.public_view(state)["averages"]]
    assert any("Uber" in label for label in labels)
    assert any("Restaurante" in label for label in labels)
    seen = set()
    for _ in range(12):
        event = engine._pick_event(state, __import__("random").Random(1))
        assert event
        seen.add(event["title"])
        state["pending_event"] = None
    blob = " ".join(seen).lower()
    assert "chiria" not in blob
    assert "spălat" not in blob
    assert "grecia" not in blob
    assert all(event_title.startswith("Taie ") for event_title in seen)
    assert any(word in blob for word in ("uber", "restaurant", "pariuri", "livrări", "paypo", "numerar"))


def test_accepting_a_cut_removes_it_from_monthly_expenses():
    stats = summarize(_statement_text())
    profile = {
        "name": "Matei Pop",
        "income": {"salary": stats["venit_mediu"]},
        "home": {"housing": 0},
        "bank": {"cash": 500, "savings": 0},
        "categories": [{"id": c["id"], "label": c["label"], "institution": c["institution"], "monthly": c["medie_lunara"]}
                       for c in stats["categorii"]],
        "statement_months": 12,
        "goal": {"description": "Fond de urgență", "target_amount": 5000, "horizon_months": 12},
    }
    state = engine.new_game(profile, seed=3)
    before = engine.monthly_expenses(state)
    uber = engine._expense(state, "market", "uber")
    event = engine._pick_event(state, __import__("random").Random(1))
    assert event["kind"] == "suggestion"
    assert event["id"] == "taie_uber"
    state["pending_event"] = event
    engine.choose(state, event["options"][0]["id"])
    assert engine._expense(state, "market", "uber") == 0
    assert abs(engine.monthly_expenses(state) - (before - uber)) < 1
    assert all(row["id"] != "uber" for row in engine.public_view(state)["averages"])


def test_statement_patch_fills_profile_from_averages():
    stats = summarize(_statement_text())
    analysis = {
        "titular": stats["titular"],
        "venit_lunar_estimat": stats["venit_mediu"],
        "sold_final": stats["sold_final"],
        "economii_identificate": 0,
        "medii_lunare": stats["categorii"],
        "luni_analizate": stats["luni"],
        "profil_din_extras": {"varsta": 21, "ocupatie": stats["ocupatie"], "locuinta": "parinti",
                              "alte_intrari_medii": stats["alte_intrari_medii"]},
    }
    patch = onboarding.statement_patch(analysis, {"name": "Matei Pop", "loans": []})
    assert patch["home"]["housing"] == 0
    assert patch["market"]["transport"] == next(c["medie_lunara"] for c in stats["categorii"] if c["id"] == "uber")
    assert patch["categories"]
    assert patch["statement_months"] == 12
