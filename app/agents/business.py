"""Agent 4: AI accountant at the Business institution. Analyses uploaded documents (registration dossier, expense
invoices), compares tax regimes with the deterministic calculator, keeps the fiscal calendar, cites the law (RAG) and
can apply the business plan to the game."""
import json

from ..demo import engine
from . import dossier, legal, memory, store, taxes
from .consultant import financial_state
from .llm import Tool, add_user_text, chat_turn

MAX_DOC_CHARS = 15000

GREETING = ("Bună! Sunt contabilul AI de la Afacere. Te ajut să alegi între PFA și SRL, îți calculez taxele pentru 2026 "
            "și îți țin calendarul fiscal. Încarcă cu 📎 documentele: dosarul pentru ONRC (cerere, act constitutiv, "
            "dovada sediului) ți-l verific, iar la facturile de cheltuieli îți spun ce e deductibil. "
            "Pentru reguli, caut direct în Codul fiscal și în Codul de procedură fiscală.")

SYSTEM = """Ești contabilul AI din clădirea „Afacere” din Raiff Quest (joc educațional Raiffeisen Bank).
Ajuți utilizatorul să-și deschidă și să-și administreze o mică afacere în România, în anul fiscal 2026.

Ce faci:
- Afli ideea de afacere, veniturile și cheltuielile estimate, dacă ar avea angajați, de ce capital are nevoie.
- Calculezi taxele DOAR cu compare_tax_regimes și calculate_taxes (nu calcula de cap). Explică simplu cât plătește și cât îi rămâne lunar.
- Termene: folosește fiscal_calendar pentru datele concrete (D100, D112, Declarația unică, bilanț, D101) și explică ce se întâmplă la întârziere.
- Legislație: pentru orice regulă (deductibilitate, termene, penalități, amenzi, documente ONRC, praguri), caută cu search_legislation
  și citează articolul („Codul fiscal, art. 25 alin. (3)”). Nu inventa articole; dacă nu găsești, spune că trebuie verificat.
- Dosarul ONRC: când utilizatorul încarcă documente de înființare, apelează review_dossier și explică ce e complet, ce e doar menționat
  dar neîncărcat și ce lipsește. Citește și conținutul: verifică dacă denumirea, sediul, asociatul și codul CAEN sunt aceleași în toate documentele,
  dacă actul de spațiu e valabil și dacă există semnături.
- Facturi de cheltuieli: identifică fiecare poziție, alege categoria și apelează classify_expense pentru fiecare poziție importantă.
  Spune ce e deductibil, în ce procent, în ce categorie și ce economie de impozit aduce. Atenție la micro: cheltuielile nu reduc impozitul de 1%.
- Când primești <document>, spune întâi pe scurt ce tip de document e și cifrele cheie, apoi aplică regulile de mai sus.
- Ține cont de situația lui personală (get_financial_state) și de fișa comună: dacă afacerea îi pune în pericol bugetul sau scopul, spune-o.
- Când utilizatorul vrea să pornească afacerea în joc, confirmă cifrele și apelează apply_business_to_game.
  În joc, taxele se acumulează lunar și se plătesc la termenele din calendar; dacă amână, plătește dobânzi, penalități și amendă.
- {memory_rule}
- Răspunsuri în română, clare, cu liste scurte, maximum ~200 de cuvinte, cu cifrele principale în lei.
- Ești un asistent educațional: încheie calculele importante cu nota că sunt orientative și trebuie verificate cu un expert contabil.

Profilul utilizatorului: {profile}
Documente încărcate până acum: {documents}

{memory}
"""


def _tools(session_id: str, convo: dict) -> list[Tool]:
    def compare_tax_regimes(annual_revenue: float, annual_expenses: float, owner_is_employee: bool = True):
        return taxes.compare(annual_revenue, annual_expenses, owner_is_employee)

    def calculate_taxes(regime: str, annual_revenue: float, annual_expenses: float, owner_is_employee: bool = True):
        return taxes.calculate(regime, annual_revenue, annual_expenses, owner_is_employee)

    def startup_checklist(form: str):
        return taxes.checklist(form)

    def get_financial_state():
        return financial_state(session_id)

    def fiscal_calendar(form: str, regime: str = "micro", has_salaried: bool = True, vat_payer: bool = False,
                        d112_quarterly: bool = True, months: int = 12):
        game = store.load(session_id, "game")
        if game:
            year, month = engine.calendar(game, game["month"] + 1)
        else:
            year, month = engine._next_month(engine.date.today())
        return taxes.fiscal_calendar(form, regime, year, month, min(max(months, 1), 24), has_salaried, vat_payer, d112_quarterly)

    def search_legislation(query: str, law: str | None = None, article: str | None = None):
        return legal.search(query, law, article)

    def review_dossier(form: str):
        return dossier.review(form, convo["documents"])

    def classify_expense(category: str, amount: float, regime: str, vat_payer: bool = False, business_share: float = 1.0):
        return taxes.classify_expense(category, amount, regime, vat_payer, business_share)

    def apply_business_to_game(name: str, form: str, regime: str, startup_cost: float,
                               monthly_revenue: float, monthly_expenses: float, owner_is_employee: bool = True,
                               d112_quarterly: bool = True):
        game = store.load(session_id, "game")
        if not game:
            return {"error": "Jocul nu a pornit încă."}
        if game.get("business"):
            return {"error": f"Ai deja o afacere activă: {game['business']['name']}."}
        regime = "pfa" if form.upper() == "PFA" else regime
        result = taxes.calculate(regime, monthly_revenue * 12, monthly_expenses * 12, owner_is_employee)
        monthly_taxes = round(result["total_taxe"] / 12, 2)
        business = {"name": name, "form": form.upper(), "regime": regime, "regime_label": result["denumire"],
                    "startup_cost": float(startup_cost), "monthly_revenue": float(monthly_revenue),
                    "monthly_expenses": float(monthly_expenses), "monthly_taxes": monthly_taxes,
                    "monthly_net": result["bani_in_mana_lunar"],
                    "monthly_cash": round(result["bani_in_mana_lunar"] + monthly_taxes, 2),
                    "obligations": taxes.obligations(regime, result, d112_quarterly)}
        engine.set_business(game, business)
        freelance = engine._find_item(game, "business", "freelance")
        if freelance:
            game["items"]["business"].remove(freelance)
        store.save(session_id, "game", game)
        memory.add(session_id, "business", "afacere",
                   f"A pornit în joc „{name}” ({result['denumire']}): venit {monthly_revenue:.0f} lei/lună, "
                   f"net după taxe {result['bani_in_mana_lunar']:.0f} lei/lună.")
        view = engine.fiscal_view(game)
        return {"ok": True, "afacere": business, "termene": view["obligations"],
                "summary": f"„{name}” pornită în joc: cost inițial {engine.money(startup_cost)}, "
                           f"{engine.money(business['monthly_cash'])}/lună înainte de taxe, taxe de {engine.money(monthly_taxes)}/lună plătite la termen"}

    num = {"type": "number"}
    regime = {"type": "string", "enum": ["pfa", "micro", "profit"], "description": "pfa = PFA sistem real, micro = SRL micro 1%, profit = SRL impozit pe profit 16%"}
    owner = {"type": "boolean", "description": "la SRL: proprietarul e angajat cu salariul minim (implicit da)"}
    form = {"type": "string", "enum": ["PFA", "SRL"]}
    return [
        Tool("compare_tax_regimes", "Compară PFA, SRL micro și SRL impozit pe profit pentru venituri/cheltuieli ANUALE (lei), regulile din 2026.",
             {"type": "object", "properties": {"annual_revenue": num, "annual_expenses": num, "owner_is_employee": owner},
              "required": ["annual_revenue", "annual_expenses"]}, compare_tax_regimes),
        Tool("calculate_taxes", "Calcul detaliat de taxe pentru un singur regim, pe sume ANUALE (lei).",
             {"type": "object", "properties": {"regime": regime, "annual_revenue": num, "annual_expenses": num, "owner_is_employee": owner},
              "required": ["regime", "annual_revenue", "annual_expenses"]}, calculate_taxes),
        Tool("fiscal_calendar", "Termenele fiscale concrete (date) din următoarele luni pentru forma și regimul ales, plus ce se întâmplă la întârziere.",
             {"type": "object", "properties": {"form": form, "regime": regime, "has_salaried": {"type": "boolean"},
                                               "vat_payer": {"type": "boolean"}, "d112_quarterly": {"type": "boolean"},
                                               "months": {"type": "integer"}}, "required": ["form"]}, fiscal_calendar),
        Tool("search_legislation", "Caută în textul oficial consolidat al Codului fiscal, Codului de procedură fiscală și Legii 265/2022 (registrul comerțului).",
             {"type": "object", "properties": {
                 "query": {"type": "string", "description": "cuvinte cheie în română, ex. „cheltuieli protocol limita 2% profit”"},
                 "law": {"type": "string", "enum": list(legal.LAWS)},
                 "article": {"type": "string", "description": "număr de articol, dacă îl știi (ex. 25, 68, 174)"}},
              "required": ["query"]}, search_legislation),
        Tool("review_dossier", "Verifică documentele încărcate pentru dosarul de înființare ONRC (PFA sau SRL): ce e încărcat, menționat sau lipsă.",
             {"type": "object", "properties": {"form": form}, "required": ["form"]}, review_dossier),
        Tool("classify_expense", "Deductibilitatea unei cheltuieli: procent, sumă deductibilă, economie de impozit, regula legală.",
             {"type": "object", "properties": {
                 "category": {"type": "string", "enum": taxes.EXPENSE_CATEGORIES}, "amount": {"type": "number", "description": "lei, fără TVA"},
                 "regime": regime, "vat_payer": {"type": "boolean"},
                 "business_share": {"type": "number", "description": "pentru folosire mixtă: fracția folosită în activitate (0-1)"}},
              "required": ["category", "amount", "regime"]}, classify_expense),
        Tool("startup_checklist", "Pașii, documentele și costurile orientative pentru înființarea unui PFA sau SRL.",
             {"type": "object", "properties": {"form": form}, "required": ["form"]}, startup_checklist),
        Tool("get_financial_state", "Situația financiară personală curentă a utilizatorului din joc.",
             {"type": "object", "properties": {}}, get_financial_state),
        Tool("apply_business_to_game", "Pornește afacerea în joc: cheltuie costul inițial, adaugă lunar încasările și programează taxele la termene.",
             {"type": "object", "properties": {
                 "name": {"type": "string"}, "form": form, "regime": regime,
                 "startup_cost": num, "monthly_revenue": num, "monthly_expenses": num, "owner_is_employee": owner,
                 "d112_quarterly": {"type": "boolean"}},
              "required": ["name", "form", "regime", "startup_cost", "monthly_revenue", "monthly_expenses"]}, apply_business_to_game),
        memory.tool(session_id, "business"),
    ]


def new_conversation() -> dict:
    return {"history": [], "display": [{"role": "assistant", "text": GREETING}], "documents": []}


def _system(session_id: str, convo: dict) -> str:
    profile = store.load(session_id, "profile", {}).get("data", {})
    docs = ", ".join(f"{d['name']} ({', '.join(d.get('kinds', [])) or 'tip nedetectat'})" for d in convo["documents"]) or "niciunul"
    return SYSTEM.format(profile=json.dumps(profile, ensure_ascii=False), documents=docs,
                         memory=memory.prompt_block(session_id), memory_rule=memory.RULE)


def user_turn(session_id: str, convo: dict, text: str):
    convo["display"].append({"role": "user", "text": text})
    add_user_text(convo["history"], text)
    yield from chat_turn(convo, _system(session_id, convo), _tools(session_id, convo), max_tokens=2000)


def document_turn(session_id: str, convo: dict, filename: str, text: str, method: str, note: str = ""):
    kinds = dossier.classify(text)
    convo["documents"].append({"name": filename, "chars": len(text), "method": method, "kinds": kinds, "text": text[:MAX_DOC_CHARS]})
    convo["display"].append({"role": "system", "text": f"📎 Document încărcat: „{filename}” ({len(text)} caractere, {method})"
                                                       + (f", tip detectat: {', '.join(kinds)}" if kinds else "") + "."
                                                       + (f" Mesaj: {note}" if note else "")})
    memory.add(session_id, "business", "documente", f"A încărcat la contabil „{filename}”" + (f" ({', '.join(kinds)})" if kinds else "") + ".")
    add_user_text(convo["history"],
                  f"<document nume=\"{filename}\" metoda_extragere=\"{method}\" tip_detectat=\"{', '.join(kinds) or 'necunoscut'}\">\n"
                  f"{text[:MAX_DOC_CHARS]}\n</document>\n"
                  + (note or "Analizează acest document ca un contabil și spune-mi ce înseamnă pentru afacerea mea."))
    yield from chat_turn(convo, _system(session_id, convo), _tools(session_id, convo), max_tokens=2000)
