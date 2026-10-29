"""The fictional student statement: 12 months, category averages, habit events instead of rent and appliances."""
import importlib.util
from pathlib import Path

from app.agents import onboarding
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
    assert stats["bursa_medie"] == 800
    assert "bursa" not in by_id
    assert stats["cheltuieli_medii"] > stats["venit_mediu"] + stats["alte_intrari_medii"]
    assert by_id["uber"] + by_id["restaurante"] > stats["venit_mediu"] * 0.5
    assert "chirie" not in {c["id"] for c in stats["categorii"]}






def test_scholarship_is_income_shown_at_education():
    from app.schemas import Profile
    from app.sim import adapter

    profile = Profile.model_validate({
        "name": "Matei Pop", "age": 21,
        "goal": {"type": "fond_urgenta", "description": "Fond", "target_amount": 5000, "horizon_months": 12},
        "income": {"salary": 1800, "other": 450},
        "recurring": {},
        "savings": 0, "cash": 100, "debts": [], "risk_tolerance": "mediu",
        "education": {"status": "student", "scholarship": 800},
        "categories": [
            {"id": "uber", "label": "Transport (Uber / Bolt)", "institution": "market", "monthly": 100},
            {"id": "bursa", "label": "Bursă de facultate", "institution": "education", "monthly": 800},
        ],
    })
    sim, _rng = adapter.profile_to_state(profile, "matei")
    assert sim["side_income"] == 1250
    assert sim["living"] == 100
    state = adapter.to_game_state("s", sim, profile, 0, [], [])
    assert [c.id for c in state.categories if c.institution == "education"] == ["bursa"]


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
                              "alte_intrari_medii": stats["alte_intrari_medii"],
                              "bursa_medie": stats["bursa_medie"]},
    }
    patch = onboarding.statement_patch(analysis, {"name": "Matei Pop", "loans": []})
    assert patch["home"]["housing"] == 0
    assert patch["income"]["scholarship"] == 800
    bursa = next(c for c in patch["categories"] if c["id"] == "bursa")
    assert bursa["institution"] == "education" and bursa["monthly"] == 800
    assert patch["market"]["transport"] == next(c["medie_lunara"] for c in stats["categorii"] if c["id"] == "uber")
    assert patch["categories"]
    assert patch["statement_months"] == 12
