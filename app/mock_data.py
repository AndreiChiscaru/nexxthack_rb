"""Mock fixtures so the frontend can work before the real engine/agents exist."""
from .schemas import Profile

# TODO(real): produced by the onboarding agent's submit_profile tool.
ANDREI_PROFILE = Profile.model_validate({
    "name": "Andrei",
    "age": 22,
    "goal": {"type": "avans_casa", "description": "Avans de 15% pentru un apartament în Cluj", "target_amount": 25000, "horizon_months": 36},
    "income": {"salary": 4300, "other": 0},
    "recurring": {"rent": 1500, "utilities": 350, "subscriptions": 120, "transport": 200},
    "spending": {"food": 1200, "leisure": 400},
    "savings": 1200, "investments": 0, "cash": 4000,
    "debts": [{"name": "Credit nevoi personale", "monthly": 650, "remaining": 11000, "apr": 0.14}],
    "education": {"status": "student", "scholarship": 0, "tuition_monthly": 0},
    "health": {"insured": False},
    "business_interest": False,
    "risk_tolerance": "medie",
    "dependents": 0,
    "source": {"statement_uploaded": True, "statement_score": 58, "risk_signals": ["Rată la IFN"]},
})
