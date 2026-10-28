"""Agent 1: builds the player profile and goal through conversation; receives the statement agent's report."""
import json

from . import memory
from . import profile as prof
from .llm import Tool, add_user_text, chat_turn

GREETING = (
    "Salut! Îți construiesc parcursul în Raiff Quest. Ce scop financiar ai? De exemplu: „avans pentru apartament în 3 ani”. "
    "Dacă nu ai unul, te ajut eu.\n\n"
    "Poți încărca un extras (📎) sau apăsa „Pornește cu extrasul de student”, ca să-ți pun mai puține întrebări."
)

SYSTEM = """Ești agentul de onboarding din Raiff Quest, un joc educațional despre bani (tema: Raiffeisen Bank).
Rolul tău: să construiești, prin conversație, profilul financiar complet al utilizatorului și scopul lui, din care se generează parcursul în joc.
Mesajul de bun venit a fost deja afișat utilizatorului (l-ai invitat să-și spună scopul sau să încarce un extras de cont).

Cum lucrezi:
- Vorbește în română, cald și simplu, fără jargon.
- FII SCURT: maximum 2-3 propoziții scurte pe mesaj (sub ~50 de cuvinte). Fără introduceri, fără să repeți ce a spus utilizatorul,
  fără mulțumiri la fiecare mesaj. O confirmare de 3-5 cuvinte („Notat!”, „Perfect, am salvat.”) e suficientă.
- Pune maximum 2 întrebări odată, formulate scurt (ex. „Cât dai pe chirie și pe utilități?”). Nu cere ce știi deja.
- După FIECARE mesaj al utilizatorului care conține informații, apelează imediat update_profile cu tot ce ai aflat.
  Unealta îți întoarce lista câmpurilor obligatorii care lipsesc: întreabă doar de acestea (și, dacă e firesc, de cele opționale relevante).
- Toate sumele sunt în lei pe lună; convertește tu sumele anuale/săptămânale. Dacă utilizatorul spune „nu am” sau „zero”, salvează 0.
- Scopul trebuie să fie concret: descriere, sumă totală (lei) și termen (luni). Dacă e vag („vreau să economisesc”), ajută-l să-l precizeze.
- Dacă utilizatorul NU are un scop: pune 3-4 întrebări scurte despre situația lui (vârstă, ocupație, ce îl stresează la bani, ce și-ar dori în 1-3 ani),
  apoi propune 2-3 scopuri concrete potrivite, cu sumă și termen, și lasă-l să aleagă.
- Toleranța la risc: întreabă simplu („Dacă investiția ta scade 10%: vinzi, aștepți sau cumperi mai mult?”) și mapează la scazuta/medie/ridicata.
- Când primești un mesaj <raport_agent_extras>, el vine de la agentul care a analizat extrasul de cont, nu de la utilizator.
  Câmpurile sigure din el (nume, venit, sold, economii, credite) sunt deja salvate. Dacă raportul are medii_lunare, acele medii
  (lei/lună, pe toată perioada) sunt deja salvate în profil: transport, mâncare, ieșiri, abonamente, iar chiria și utilitățile sunt 0
  dacă stă cu părinții. Nu le modifica și nu cere confirmarea sumelor. Spune-i media pe categorii, în lei pe lună, și 1-2 semnale
  din obiceiurile lui (Uber, restaurante, pariuri, rate, numerar), fără să-l judeci. Aici poți folosi până la ~80 de cuvinte, ca listă scurtă.
- Nu da sfaturi de investiții sau recomandări de produse: de asta se ocupă consultantul financiar din joc.
- Când nu mai lipsește niciun câmp obligatoriu: fă un rezumat de 2-3 rânduri scurte (scop, venit, cheltuieli, economii)
  și apelează finish_onboarding. Apoi spune-i că poate apăsa „Începe jocul”.
- {memory_rule} Exemple: vrea să-și deschidă o firmă, așteaptă un copil, schimbă jobul, are o datorie care îl stresează.

Profilul curent (JSON):
{profile}

Câmpuri obligatorii lipsă: {missing}

{memory}
"""


def _system(session_id: str, profile: dict) -> str:
    missing = prof.missing(profile)
    return SYSTEM.format(profile=json.dumps(profile["data"], ensure_ascii=False),
                         missing=", ".join(missing) if missing else "niciunul — poți finaliza",
                         memory=memory.prompt_block(session_id), memory_rule=memory.RULE)


def _tools(session_id: str, profile: dict, convo: dict) -> list[Tool]:
    def update_profile(**patch):
        updated = prof.merge(profile, patch, "conversație")
        missing = prof.missing(profile)
        return {"actualizat": updated, "lipsesc": missing, "complet": not missing,
                "summary": f"{len(updated)} câmpuri salvate; lipsesc {len(missing)}" + (f": {', '.join(missing)}" if missing else "")}

    def finish_onboarding(summary: str, scenario_title: str):
        missing = prof.missing(profile)
        if missing:
            return {"error": "Profil incomplet", "lipsesc": missing}
        convo["done"] = True
        convo["scenario"] = {"title": scenario_title, "summary": summary}
        memory.add(session_id, "onboarding", "scop", f"Parcurs: {scenario_title}. {summary}")
        return {"ok": True, "summary": f"Profil complet: „{scenario_title}”"}

    return [
        memory.tool(session_id, "onboarding"),
        Tool("update_profile", "Salvează în profil informațiile aflate (doar câmpurile noi sau corectate).",
             prof.UPDATE_SCHEMA, update_profile),
        Tool("finish_onboarding", "Finalizează profilul când nu mai lipsește niciun câmp obligatoriu.",
             {"type": "object", "properties": {
                 "summary": {"type": "string", "description": "rezumat de 3-4 rânduri al situației și scopului"},
                 "scenario_title": {"type": "string", "description": "titlu scurt pentru parcurs, ex. „Avans pentru apartament în Cluj”"}},
              "required": ["summary", "scenario_title"]},
             finish_onboarding),
    ]


def new_conversation() -> dict:
    return {"history": [], "display": [{"role": "assistant", "text": GREETING}], "done": False, "scenario": None}


def user_turn(session_id: str, profile: dict, convo: dict, text: str):
    convo["display"].append({"role": "user", "text": text})
    add_user_text(convo["history"], text)
    yield from chat_turn(convo, _system(session_id, profile), _tools(session_id, profile, convo))


def statement_patch(analysis: dict, game_profile: dict) -> dict:
    """Fields the statement knows with confidence. Category averages are counted from the transactions."""
    patch: dict = {"income": {}, "bank": {}, "market": {}, "home": {}}
    persona = analysis.get("profil_din_extras") or {}
    if analysis.get("titular"):
        patch["name"] = game_profile.get("name")
    if persona.get("varsta"):
        patch["age"] = int(persona["varsta"])
    if persona.get("ocupatie"):
        patch["occupation"] = persona["ocupatie"]
    if analysis.get("venit_lunar_estimat") is not None:
        patch["income"]["salary"] = analysis["venit_lunar_estimat"]
    if persona.get("alte_intrari_medii"):
        patch["income"]["other"] = persona["alte_intrari_medii"]
    if analysis.get("sold_final") is not None:
        patch["bank"]["cash"] = float(analysis["sold_final"])
    if analysis.get("economii_identificate") is not None:
        patch["bank"]["savings"] = analysis["economii_identificate"]
    elif analysis.get("medii_lunare"):
        patch["bank"]["savings"] = 0
    loans = game_profile.get("loans") or []
    if loans:
        patch["bank"]["debts"] = [{"name": l["name"], "monthly_payment": l["payment"], "remaining": l["principal"], "apr": l["apr"]}
                                  for l in loans]
    cats = analysis.get("medii_lunare") or []
    if cats:
        by_id = {c["id"]: c["medie_lunara"] for c in cats}
        patch["categories"] = [{"id": c["id"], "label": c["label"], "institution": c["institution"], "monthly": c["medie_lunara"]}
                               for c in cats]
        patch["statement_months"] = int(analysis.get("luni_analizate") or 0)
        patch["market"]["transport"] = by_id.get("uber", 0)
        patch["market"]["food"] = by_id.get("alimente", 0)
        patch["market"]["leisure"] = round(sum(by_id.get(k, 0) for k in (
            "restaurante", "livrari", "cafea", "cumparaturi", "pariuri", "rate", "numerar")), 2)
        patch["home"]["subscriptions"] = round(by_id.get("abonamente", 0) + by_id.get("telefon", 0), 2)
    if persona.get("bursa_medie"):
        patch["income"]["scholarship"] = persona["bursa_medie"]
        patch.setdefault("categories", []).append({
            "id": "bursa", "label": "Bursă de facultate", "institution": "education",
            "monthly": persona["bursa_medie"],
        })
    if persona.get("locuinta") == "parinti":
        patch["home"]["housing"] = 0
        patch["home"]["utilities"] = 0
        patch["education"] = {"status": "student"}
    return patch


def statement_report(analysis: dict) -> dict:
    keys = ["titular", "banca", "perioada", "moneda", "sold_initial", "sold_final", "total_intrari", "total_iesiri",
            "venit_lunar_estimat", "cheltuieli_lunare_estimate", "economii_identificate", "venituri",
            "cheltuieli_pe_categorii", "medii_lunare", "luni_analizate", "obligatii_recurente",
            "grad_indatorare_procent", "semnale_de_risc",
            "puncte_forte", "scor_stabilitate_financiara", "nivel_risc", "rezumat", "observatii_calitate_date"]
    return {k: analysis.get(k) for k in keys}


def statement_turn(session_id: str, profile: dict, convo: dict, filename: str, analysis: dict, game_profile: dict):
    saved = prof.merge(profile, statement_patch(analysis, game_profile), "extras")
    score = analysis.get("scor_stabilitate_financiara")
    averages = analysis.get("medii_lunare") or []
    months = analysis.get("luni_analizate")
    listed = ", ".join(f"{c['label']} {c['medie_lunara']:.0f} lei" for c in averages[:6])
    convo["display"].append({"role": "system", "text": f"📄 Agentul de analiză a citit „{filename}”: scor de stabilitate {score}/100, "
                                                        f"risc {analysis.get('nivel_risc', '-')}. A completat automat {len(saved)} câmpuri."
                                                        + (f" Medii pe {months} luni: {listed}." if listed else "")})
    memory.add(session_id, "statement", "risc",
               f"Extras „{filename}”: scor {score}/100, risc {analysis.get('nivel_risc', '-')}. "
               + "; ".join((analysis.get("semnale_de_risc") or [])[:3]))
    report = json.dumps(statement_report(analysis), ensure_ascii=False)
    add_user_text(convo["history"],
                  f"<raport_agent_extras fisier=\"{filename}\">\n{report}\n</raport_agent_extras>\n"
                  f"Câmpuri salvate automat din extras: {', '.join(saved) or 'niciunul'}. "
                  "Continuă conversația cu utilizatorul pe baza raportului.")
    yield from chat_turn(convo, _system(session_id, profile), _tools(session_id, profile, convo))
