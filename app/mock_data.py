"""Mock fixtures so the frontend can work before the real engine/agents exist."""
from .schemas import (
    INSTITUTIONS,
    Balance,
    Event,
    GameState,
    GoalProgress,
    InstitutionStatus,
    LogEntry,
    Monthly,
    MonthlyExpenses,
    Product,
    ProductHolding,
    Profile,
    Wellbeing,
)

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

# Order in which the mock onboarding "collects" required fields (§4.1).
REQUIRED_FIELDS = ["goal", "age", "income.salary", "recurring", "savings", "debts", "risk_tolerance"]
# TODO(real): read from the session's profile.goal.horizon_months.
MOCK_HORIZON_MONTHS = 36


def recompute(state: GameState) -> None:
    """Refresh derived fields (net worth, goal progress) after any change."""
    # TODO(real): app/sim/engine.py owns these formulas (port of finance_sim.gd).
    b = state.balance
    b.net_worth = round(b.cash + b.savings + b.investments - b.debt, 2)
    state.goal.progress = round(min(1.0, max(0.0, b.savings / state.goal.target_amount)), 3)
    state.goal.on_track = state.goal.progress >= state.month / MOCK_HORIZON_MONTHS
    state.products = [ProductHolding(id="cont_economii", balance=b.savings)] if b.savings > 0 else []


def initial_state(session_id: str, profile: Profile) -> GameState:
    # TODO(real): built by app/sim/engine.py from the profile.
    r, s = profile.recurring, profile.spending
    state = GameState(
        session_id=session_id,
        month=0,
        age=profile.age,
        goal=GoalProgress(type=profile.goal.type, target_amount=profile.goal.target_amount, progress=0, on_track=True),
        balance=Balance(
            cash=profile.cash, savings=profile.savings, investments=profile.investments,
            debt=sum(d.remaining for d in profile.debts), net_worth=0,
        ),
        monthly=Monthly(
            income=profile.income.salary + profile.income.other,
            expenses=MonthlyExpenses(
                home=r.rent + r.utilities + r.subscriptions,
                market=s.food + s.leisure + r.transport,
                education=profile.education.tuition_monthly,
                health=0,
                business=0,
                bank=sum(d.monthly for d in profile.debts),
            ),
        ),
        wellbeing=Wellbeing(stress=40, confidence=50),
        institutions=[InstitutionStatus(id=i, pending_events=0) for i in INSTITUTIONS],
        products=[],
        log=[LogEntry(month=0, institution="home", text=f"{profile.name or 'Jucătorul'} începe aventura.")],
    )
    recompute(state)
    return state


# TODO(real): data/events.json + scheduler; 2-4 events per institution.
EVENTS: list[Event] = [Event.model_validate(e) for e in [
    {"id": "chirie_marita", "institution": "home", "title": "Chiria crește",
     "text": "Proprietarul anunță o creștere a chiriei cu 200 lei de luna viitoare.",
     "options": [{"id": "accept", "label": "Accept creșterea", "ops": {"living_add": 200, "mood": {"stress": 4}}},
                 {"id": "move", "label": "Mă mut în ceva mai mic", "ops": {"spend": 800, "living_add": -100, "mood": {"stress": 8}}}]},
    {"id": "frigider_stricat", "institution": "home", "title": "Frigiderul s-a stricat",
     "text": "Frigiderul nu mai răcește. Reparația sau unul nou?",
     "options": [{"id": "repair", "label": "Repar (450 lei)", "ops": {"spend": 450}},
                 {"id": "new_rates", "label": "Iau unul nou în rate", "ops": {"loan": {"name": "Rate frigider", "principal": 2400, "apr": 0, "months": 12}}}]},
    {"id": "black_friday", "institution": "market", "title": "Black Friday",
     "text": "Reduceri mari la electronice. Laptopul tău e vechi.",
     "options": [{"id": "buy", "label": "Cumpăr laptop (3.500 lei)", "ops": {"spend": 3500, "mood": {"conf": 3}}},
                 {"id": "skip", "label": "Mai aștept", "ops": {"mood": {"stress": -1}}}]},
    {"id": "preturi_cresc", "institution": "market", "title": "Prețurile cresc",
     "text": "Inflația împinge coșul lunar în sus cu 150 lei.",
     "options": [{"id": "absorb", "label": "Plătesc diferența", "ops": {"living_add": 150}},
                 {"id": "budget", "label": "Gătesc mai mult acasă", "ops": {"living_add": 50, "mood": {"stress": 2}}}]},
    {"id": "curs_certificare", "institution": "education", "title": "Curs de certificare",
     "text": "Un curs de cloud de 3 luni ți-ar putea crește salariul.",
     "options": [{"id": "enroll", "label": "Mă înscriu (2.400 lei)", "ops": {"spend": 2400, "salary_mult": 1.1, "mood": {"conf": 6}}},
                 {"id": "skip", "label": "Nu acum", "ops": {}}]},
    {"id": "bursa_merit", "institution": "education", "title": "Bursă de merit",
     "text": "Ai prins o bursă de merit pe semestru.",
     "options": [{"id": "save_it", "label": "O pun deoparte", "ops": {"emergency_contrib": 600, "mood": {"conf": 4}}},
                 {"id": "spend_it", "label": "O cheltui", "ops": {"mood": {"conf": 2}}}]},
    {"id": "promovare", "institution": "work", "title": "Ofertă de promovare",
     "text": "Șeful îți propune un rol de team lead, cu mai multă responsabilitate.",
     "options": [{"id": "accept", "label": "Accept", "ops": {"salary_mult": 1.2, "mood": {"stress": 8, "conf": 6}}},
                 {"id": "decline", "label": "Refuz", "ops": {"mood": {"stress": -2}}}]},
    {"id": "ore_suplimentare", "institution": "work", "title": "Ore suplimentare",
     "text": "Proiect urgent: poți lucra în weekenduri luna asta.",
     "options": [{"id": "yes", "label": "Lucrez weekendurile (+900 lei)", "ops": {"spend": -900, "mood": {"stress": 10}}},
                 {"id": "no", "label": "Îmi păstrez weekendurile", "ops": {}}]},
    {"id": "idee_afacere", "institution": "business", "title": "Idee de afacere",
     "text": "Un prieten vrea să deschideți împreună o cafenea mobilă.",
     "options": [{"id": "invest", "label": "Intru cu 5.000 lei", "ops": {"spend": 5000, "mood": {"stress": 6, "conf": 5}}},
                 {"id": "pass", "label": "Refuz politicos", "ops": {}}]},
    {"id": "pfa_freelance", "institution": "business", "title": "Proiect freelance",
     "text": "Un client îți oferă un proiect pe PFA.",
     "options": [{"id": "take", "label": "Îl iau (+1.500 lei)", "ops": {"spend": -1500, "mood": {"stress": 5, "conf": 4}}},
                 {"id": "skip", "label": "Nu am timp", "ops": {}}]},
    {"id": "dentist", "institution": "hospital", "title": "Urgență stomatologică",
     "text": "O măsea te doare de câteva zile. Tratamentul costă 1.200 lei.",
     "options": [{"id": "pay_cash", "label": "Plătesc din economii", "ops": {"spend": 1200}},
                 {"id": "installments", "label": "Plată în rate", "ops": {"loan": {"principal": 1200, "apr": 0, "months": 6}}}]},
    {"id": "control_anual", "institution": "hospital", "title": "Control anual",
     "text": "Medicul de familie îți recomandă un set de analize.",
     "options": [{"id": "do_it", "label": "Fac analizele (300 lei)", "ops": {"spend": 300, "mood": {"stress": -3}}},
                 {"id": "insure", "label": "Îmi fac asigurare de sănătate", "ops": {"insurance_level": 1, "living_add": 90}}]},
    {"id": "oferta_refinantare", "institution": "bank", "title": "Ofertă de refinanțare",
     "text": "Banca îți propune refinanțarea creditului la o dobândă mai mică.",
     "options": [{"id": "refinance", "label": "Refinanțez", "ops": {"loan": {"name": "Refinanțare", "principal": 0, "apr": 0.099, "months": 36}, "mood": {"stress": -4}}},
                 {"id": "keep", "label": "Rămân pe creditul actual", "ops": {}}]},
    {"id": "economisire_automata", "institution": "bank", "title": "Economisire automată",
     "text": "Poți seta un transfer lunar automat în contul de economii.",
     "options": [{"id": "300", "label": "300 lei/lună", "ops": {"emergency_contrib": 300, "mood": {"conf": 3}}},
                 {"id": "invest", "label": "200 economii + 150 fond", "ops": {"emergency_contrib": 200, "invest_contrib": 150, "mood": {"conf": 4}}}]},
]]

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
