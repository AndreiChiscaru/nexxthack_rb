"""Mock fixtures so the frontend can work before the real engine/agents exist."""
from .schemas import Product, Profile

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

# TODO(real): data/products.json, ingested from the Raiffeisen PDF. Copied from catalog.gd.
PRODUCTS: list[Product] = [Product.model_validate(p) for p in [
    {"id": "credit_auto", "category": "credit_auto", "name": "Credit Auto Demo", "apr": 0.095, "min_months": 12, "max_months": 84,
     "note": "Dobândă anuală fictivă 9,5%, avans minim 20%.", "mock": True},
    {"id": "credit_nevoi", "category": "credit_personal", "name": "Credit de nevoi personale Demo", "apr": 0.139, "min_months": 12, "max_months": 60,
     "note": "Dobândă anuală fictivă 13,9%, fără garanții.", "mock": True},
    {"id": "card_magazin", "category": "credit_personal", "name": "Card de cumpărături Demo", "apr": 0.22, "min_months": 6, "max_months": 36,
     "note": "Dobândă anuală fictivă 22% - cea mai scumpă variantă din catalog.", "mock": True},
    {"id": "credit_business", "category": "credit_business", "name": "Credit Micro-Business Demo", "apr": 0.099, "min_months": 12, "max_months": 72,
     "note": "Dobândă anuală fictivă 9,9%, pentru echipamente și capital de lucru.", "mock": True},
    {"id": "cont_economii", "category": "savings", "name": "Cont de Economii Automat Demo", "apr": 0.03, "min_months": 0, "max_months": 0,
     "note": "Dobândă fictivă 3%/an, transfer automat lunar, bani disponibili oricând.", "mock": True},
    {"id": "depozit", "category": "savings", "name": "Depozit Flexibil Demo", "apr": 0.045, "min_months": 0, "max_months": 0,
     "note": "Dobândă fictivă 4,5%/an, pentru sume care nu sunt necesare imediat.", "mock": True},
    {"id": "fond_diversificat", "category": "investment", "name": "Fond Diversificat Demo", "apr": 0.07, "min_months": 0, "max_months": 0,
     "note": "Randament mediu estimat 7%/an (fictiv, nu e garantat; poate scădea).", "mock": True},
    {"id": "asig_complet", "category": "insurance", "name": "Pachet Protecție Complet Demo", "apr": 0.0, "min_months": 0, "max_months": 0,
     "note": "Sănătate + viață + locuință, 280 lei/lună fictivi, acoperă ~85% din costuri medicale.", "mock": True},
]]
