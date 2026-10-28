"""Agent 3: financial consultant (chat popup). Reads the profile, statement insights and live game state,
and backs every number with an engine projection."""
import json
from pathlib import Path

from ..demo import engine
from . import memory, store
from .llm import Tool, add_user_text, chat_turn

PRODUCTS = json.loads((Path(__file__).resolve().parents[2] / "data" / "products.json").read_text(encoding="utf-8"))
CATEGORIES = sorted({p["category"] for p in PRODUCTS})

GREETING = ("Sunt consultantul tău financiar. Știu scopul și situația ta și urmăresc tot ce se întâmplă în joc. "
            "Întreabă-mă orice — de exemplu „ce aleg la evenimentul ăsta?” sau „cum îmi ating scopul mai repede?”.")

SYSTEM = """Ești consultantul financiar AI din Raiff Quest, un joc educațional al Raiffeisen Bank.
Ghidezi utilizatorul spre scopul lui financiar, pe baza profilului, a analizei extrasului de cont și a stării curente din joc.

Reguli:
- Vorbește în română, prietenos, concret, fără să judeci. Maximum ~150 de cuvinte; folosește liste scurte.
- NU inventa cifre și NU face calcule de cap: orice sumă, proiecție sau comparație vine din unelte.
  Folosește get_financial_state pentru situația curentă, simulate_event_options pentru a compara opțiunile evenimentului activ,
  simulate_plan pentru planuri de economisire/investiții/reducere de cheltuieli.
- Leagă mereu sfatul de scopul utilizatorului (progres, luni rămase, dacă e pe drumul cel bun).
- Ordinea priorităților: evită descoperitul și datoriile scumpe → fond de urgență de 3-6 luni de cheltuieli esențiale →
  protecție (asigurare) → economisire automată pentru scop → investiții pe termen lung (doar cu fond de urgență și orizont de peste 3 ani),
  ținând cont de toleranța la risc.
- Recomandă produse bancare DOAR din catalogul Raiffeisen (search_products), cu numele exact. Catalogul reflectă oferta publică la 28 octombrie 2026.
  Spune de ce i se potrivește, condiția care i se aplică (vârstă, venit, încasarea salariului la bancă, avans, certificat energetic) și avertismentul din câmpul cautions.
  Dobânzile sunt „de la” și cele mai bune cer de obicei statut Premium, încasarea venitului la bancă sau o asigurare de viață. Aprobarea unui credit nu este automată.
  Dobânda la economii și depozite e brută și se impozitează cu 10%. Depozitele sunt garantate; fondurile, SmartInvest și asigurările cu componentă investițională nu au randament garantat.
  Simulările din joc folosesc dobânzi simplificate (economii 4%/an, investiții în jur de 6%, descoperit 22%). Când recomanzi un produs real, spune că cifra din joc nu este oferta băncii.
  Nu inventa dobânzi, comisioane sau sume de bonus care nu apar în catalog.
- Când există un eveniment activ și utilizatorul cere sfat, compară opțiunile cu simulate_event_options și spune clar ce ai alege și de ce.
- Încheie, când e relevant, cu un singur pas concret pe care îl poate face acum în joc (ex. „Setează la Bancă un transfer automat de 500 lei/lună”).
- Dacă are o afacere în joc, ține cont de taxele acumulate și de următoarele termene fiscale (sunt în get_financial_state):
  banii pentru taxe nu sunt bani de cheltuit. Pentru întrebări fiscale detaliate, trimite-l la contabilul AI de la Afacere.
- Folosește fișa comună: dacă alt agent a aflat ceva (ex. vrea să-și deschidă o firmă), ține cont fără să întrebi din nou.
- {memory_rule}
- E un ghid educațional, nu o ofertă personalizată și nu o aprobare de credit: prezintă condițiile din catalog și spune că decizia și costul final le confirmă banca. Nu garanta randamente.

Profilul utilizatorului: {profile}
Analiza extrasului de cont (dacă există): {statement}

{memory}
"""


def financial_state(session_id: str) -> dict:
    profile = store.load(session_id, "profile", {}).get("data", {})
    game = store.load(session_id, "game")
    if not game:
        return {"joc_pornit": False, "profil": profile, "summary": "Jocul nu a pornit încă; am doar profilul."}
    view = engine.public_view(game)
    event = game.get("pending_event")
    return {
        "joc_pornit": True,
        "luna": game["month"],
        "data_calendaristica": view["calendar"],
        "fiscal": view["fiscal"] if game.get("business") else None,
        "scop": view["goal"],
        "solduri": {k: view["balance"][k] for k in ("cash", "savings", "investments", "debt", "net_worth")},
        "lunar": view["monthly"],
        "pe_institutii": [{"institutie": i["name"], "intrari": i["in"], "iesiri": i["out"],
                           "detalii": [f"{it['label']}: {it['amount']:+.0f}" for it in i["items"]]} for i in view["institutions"]],
        "credite": [{"nume": d["name"], "sold": round(d["balance"]), "dobanda": d["apr"], "rata": round(d["payment"])} for d in game["debts"]],
        "transferuri_automate": game["auto"],
        "luni_fond_urgenta": view["emergency_months"],
        "asigurat_sanatate": game["insured"],
        "afacere": game.get("business"),
        "eveniment_activ": {"titlu": event["title"], "text": event["text"], "institutie": event["institution"],
                            "optiuni": [{"id": o["id"], "eticheta": o["label"], "descriere": o["desc"]} for o in event["options"]]} if event else None,
        "istoric_recent": game["log"][-6:],
        "toleranta_risc": profile.get("risk_tolerance"),
        "summary": (f"Luna {game['month']}: progres scop {view['goal']['progress']:.0%}, surplus {engine.money(view['monthly']['surplus'])}/lună, "
                    f"fond urgență {view['emergency_months']} luni" + (f", eveniment activ: {event['title']}" if event else "")),
    }


def _tools(session_id: str) -> list[Tool]:
    def get_financial_state():
        return financial_state(session_id)

    def simulate_event_options(months: int = 12):
        game = store.load(session_id, "game")
        if not game or not game.get("pending_event"):
            return {"error": "Nu există niciun eveniment activ."}
        event = game["pending_event"]
        results = []
        for option in event["options"]:
            projection = engine.project(game, months, option.get("ops"))
            results.append({"optiune": option["label"], **projection})
        best = max(results, key=lambda r: (not r["overdraft"], r["goal_progress"], r["net_worth"]))
        return {"eveniment": event["title"], "orizont_luni": months, "rezultate": results,
                "summary": f"{len(results)} opțiuni simulate pe {months} luni; cel mai bun progres: „{best['optiune']}” ({best['goal_progress']:.0%})"}

    def simulate_plan(savings_per_month: float | None = None, investments_per_month: float | None = None,
                      reduce_expenses_per_month: float = 0, months: int = 12):
        game = store.load(session_id, "game")
        if not game:
            return {"error": "Jocul nu a pornit încă."}
        baseline = engine.project(game, months)
        ops = {"auto": {}}
        if savings_per_month is not None:
            ops["auto"]["savings"] = savings_per_month
        if investments_per_month is not None:
            ops["auto"]["investments"] = investments_per_month
        if reduce_expenses_per_month:
            ops["item_set"] = {"inst": "market", "id": "plan_cut", "label": "Reducere cheltuieli (plan)", "amount": abs(reduce_expenses_per_month)}
        plan = engine.project(game, months, ops)
        return {"orizont_luni": months, "fara_schimbari": baseline, "cu_planul": plan,
                "summary": f"Progres scop în {months} luni: {baseline['goal_progress']:.0%} → {plan['goal_progress']:.0%}; "
                           f"luni până la scop: {baseline['months_to_goal']} → {plan['months_to_goal']}"}

    def search_products(category: str):
        found = [p for p in PRODUCTS if p["category"] == category]
        if not found:
            return {"error": f"Categorie inexistentă. Alege una din: {', '.join(CATEGORIES)}"}
        return {"catalog": "Oferta publică Raiffeisen Bank la 28 octombrie 2026", "produse": found,
                "summary": f"{len(found)} produse ({category}): " + ", ".join(p["name"] for p in found)}

    return [
        Tool("get_financial_state", "Situația financiară curentă din joc: solduri, fluxuri pe instituții, credite, scop, eveniment activ.",
             {"type": "object", "properties": {}}, get_financial_state),
        Tool("simulate_event_options", "Simulează fiecare opțiune a evenimentului activ pe N luni (progres scop, patrimoniu, descoperit).",
             {"type": "object", "properties": {"months": {"type": "integer", "description": "orizont, implicit 12"}}}, simulate_event_options),
        Tool("simulate_plan", "Compară situația fără schimbări cu un plan: transfer automat la economii/investiții și/sau reducere de cheltuieli.",
             {"type": "object", "properties": {
                 "savings_per_month": {"type": "number"}, "investments_per_month": {"type": "number"},
                 "reduce_expenses_per_month": {"type": "number"}, "months": {"type": "integer"}}}, simulate_plan),
        Tool("search_products", "Caută în oferta publică Raiffeisen (credite, locuință, economii, cont, card, investiții, pensie, asigurări, campanii).",
             {"type": "object", "properties": {"category": {"type": "string", "enum": CATEGORIES}}, "required": ["category"]},
             search_products),
        memory.tool(session_id, "consultant"),
    ]


def new_conversation() -> dict:
    return {"history": [], "display": [{"role": "assistant", "text": GREETING}]}


def user_turn(session_id: str, convo: dict, text: str):
    profile = store.load(session_id, "profile", {}).get("data", {})
    statement = store.load(session_id, "statement")
    system = SYSTEM.format(profile=json.dumps(profile, ensure_ascii=False),
                           statement=json.dumps(statement["analysis"], ensure_ascii=False) if statement else "nu a fost încărcat",
                           memory=memory.prompt_block(session_id), memory_rule=memory.RULE)
    convo["display"].append({"role": "user", "text": text})
    add_user_text(convo["history"], text)
    yield from chat_turn(convo, system, _tools(session_id))
