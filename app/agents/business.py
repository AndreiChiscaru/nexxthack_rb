"""Agent 4: AI accountant at the Business institution. Analyses uploaded documents, compares tax regimes with the
deterministic calculator, guides company setup and can apply the business plan to the game."""
import json

from ..demo import engine
from . import store, taxes
from .consultant import financial_state
from .llm import Tool, add_user_text, run_agent

MAX_DOC_CHARS = 15000

GREETING = ("Bună! Sunt contabilul AI de la Afacere. Te ajut să alegi între PFA și SRL, îți calculez taxele pentru 2026 "
            "și îți analizez documentele (plan de afaceri, facturi, contracte, extrase de firmă) — încarcă-le cu 📎. "
            "Spune-mi ce idee de afacere ai și ce venituri și cheltuieli estimezi.")

SYSTEM = """Ești contabilul AI din clădirea „Afacere” din Raiff Quest (joc educațional Raiffeisen Bank).
Ajuți utilizatorul să-și deschidă și să-și administreze o mică afacere în România, în anul fiscal 2026.

Ce faci:
- Afli ideea de afacere, veniturile și cheltuielile estimate (lunar sau anual), dacă ar avea angajați, de ce capital are nevoie.
- Calculezi taxele DOAR cu uneltele compare_tax_regimes și calculate_taxes (nu calcula de cap). Explică rezultatul simplu:
  cât plătește, cât îi rămâne lunar, de ce o variantă e mai bună, ce praguri contează (plafon micro 100.000 euro, plafon TVA 395.000 lei,
  CAS doar peste 12 salarii minime la PFA, obligația unui salariat la micro).
- Dai pașii de înființare cu startup_checklist (PFA sau SRL) și spui ce documente îi trebuie.
- Când primești <document>, îl analizezi ca un contabil: ce tip de document e, cifrele cheie (venituri, cheltuieli, TVA, termene, părți),
  ce înseamnă fiscal (deductibil? TVA? riscuri? ce lipsește?) și ce ar trebui să facă mai departe. Dacă documentul are cifre de venituri/cheltuieli,
  folosește-le în calculul taxelor.
- Ții cont de situația lui personală (get_financial_state): dacă afacerea îi pune în pericol bugetul sau scopul, spune-o.
- Când utilizatorul vrea să pornească afacerea în joc, confirmă cifrele și apelează apply_business_to_game.
- Sfaturi practice: separă banii firmei (cont de firmă), pune deoparte lunar banii pentru taxe, păstrează documentele justificative,
  ia în calcul costul unui contabil. Produsele bancare le recomandă consultantul; poți menționa doar contul de firmă și creditul pentru afaceri mici (demo).
- Răspunsuri în română, clare, structurate cu liste scurte, maximum ~200 de cuvinte, cu cifrele principale formatate în lei.
- Ești un asistent educațional: încheie calculele importante cu nota că sunt orientative și trebuie verificate cu un expert contabil.

Profilul utilizatorului: {profile}
Documente încărcate până acum: {documents}
"""


def _tools(session_id: str) -> list[Tool]:
    def compare_tax_regimes(annual_revenue: float, annual_expenses: float, owner_is_employee: bool = True):
        return taxes.compare(annual_revenue, annual_expenses, owner_is_employee)

    def calculate_taxes(regime: str, annual_revenue: float, annual_expenses: float, owner_is_employee: bool = True):
        return taxes.calculate(regime, annual_revenue, annual_expenses, owner_is_employee)

    def startup_checklist(form: str):
        return taxes.checklist(form)

    def get_financial_state():
        return financial_state(session_id)

    def apply_business_to_game(name: str, form: str, regime: str, startup_cost: float,
                               monthly_revenue: float, monthly_expenses: float, owner_is_employee: bool = True):
        game = store.load(session_id, "game")
        if not game:
            return {"error": "Jocul nu a pornit încă."}
        if game.get("business"):
            return {"error": f"Ai deja o afacere activă: {game['business']['name']}."}
        result = taxes.calculate(regime, monthly_revenue * 12, monthly_expenses * 12, owner_is_employee)
        business = {"name": name, "form": form.upper(), "regime": regime, "regime_label": result["denumire"],
                    "startup_cost": float(startup_cost), "monthly_revenue": float(monthly_revenue),
                    "monthly_expenses": float(monthly_expenses), "monthly_taxes": round(result["total_taxe"] / 12, 2),
                    "monthly_net": result["bani_in_mana_lunar"]}
        engine.set_business(game, business)
        freelance = engine._find_item(game, "business", "freelance")
        if freelance:
            game["items"]["business"].remove(freelance)
        store.save(session_id, "game", game)
        return {"ok": True, "afacere": business,
                "summary": f"„{name}” pornită în joc: cost inițial {engine.money(startup_cost)}, net {engine.money(business['monthly_net'])}/lună"}

    num = {"type": "number"}
    regime = {"type": "string", "enum": ["pfa", "micro", "profit"], "description": "pfa = PFA sistem real, micro = SRL micro 1%, profit = SRL impozit pe profit 16%"}
    owner = {"type": "boolean", "description": "la SRL: proprietarul e angajat cu salariul minim (implicit da)"}
    return [
        Tool("compare_tax_regimes", "Compară PFA, SRL micro și SRL impozit pe profit pentru venituri/cheltuieli ANUALE (lei), regulile din 2026.",
             {"type": "object", "properties": {"annual_revenue": num, "annual_expenses": num, "owner_is_employee": owner},
              "required": ["annual_revenue", "annual_expenses"]}, compare_tax_regimes),
        Tool("calculate_taxes", "Calcul detaliat de taxe pentru un singur regim, pe sume ANUALE (lei).",
             {"type": "object", "properties": {"regime": regime, "annual_revenue": num, "annual_expenses": num, "owner_is_employee": owner},
              "required": ["regime", "annual_revenue", "annual_expenses"]}, calculate_taxes),
        Tool("startup_checklist", "Pașii, documentele și costurile orientative pentru înființarea unui PFA sau SRL.",
             {"type": "object", "properties": {"form": {"type": "string", "enum": ["PFA", "SRL"]}}, "required": ["form"]}, startup_checklist),
        Tool("get_financial_state", "Situația financiară personală curentă a utilizatorului din joc.",
             {"type": "object", "properties": {}}, get_financial_state),
        Tool("apply_business_to_game", "Pornește afacerea în joc: cheltuie costul inițial și adaugă lunar câștigul net după taxe.",
             {"type": "object", "properties": {
                 "name": {"type": "string"}, "form": {"type": "string", "enum": ["PFA", "SRL"]}, "regime": regime,
                 "startup_cost": num, "monthly_revenue": num, "monthly_expenses": num, "owner_is_employee": owner},
              "required": ["name", "form", "regime", "startup_cost", "monthly_revenue", "monthly_expenses"]}, apply_business_to_game),
    ]


def new_conversation() -> dict:
    return {"history": [], "display": [{"role": "assistant", "text": GREETING}], "documents": []}


def _system(session_id: str, convo: dict) -> str:
    profile = store.load(session_id, "profile", {}).get("data", {})
    docs = ", ".join(f"{d['name']} ({d['chars']} caractere)" for d in convo["documents"]) or "niciunul"
    return SYSTEM.format(profile=json.dumps(profile, ensure_ascii=False), documents=docs)


def user_turn(session_id: str, convo: dict, text: str) -> dict:
    convo["display"].append({"role": "user", "text": text})
    add_user_text(convo["history"], text)
    result = run_agent(_system(session_id, convo), convo["history"], _tools(session_id), max_tokens=2000)
    convo["display"].append({"role": "assistant", "text": result["text"], "tool_calls": result["tool_calls"]})
    return result


def document_turn(session_id: str, convo: dict, filename: str, text: str, method: str, note: str = "") -> dict:
    convo["documents"].append({"name": filename, "chars": len(text), "method": method})
    convo["display"].append({"role": "system", "text": f"📎 Document încărcat: „{filename}” ({len(text)} caractere, {method})."
                                                       + (f" Mesaj: {note}" if note else "")})
    add_user_text(convo["history"],
                  f"<document nume=\"{filename}\" metoda_extragere=\"{method}\">\n{text[:MAX_DOC_CHARS]}\n</document>\n"
                  + (note or "Analizează acest document ca un contabil și spune-mi ce înseamnă pentru afacerea mea."))
    result = run_agent(_system(session_id, convo), convo["history"], _tools(session_id), max_tokens=2000)
    convo["display"].append({"role": "assistant", "text": result["text"], "tool_calls": result["tool_calls"]})
    return result
