import json
from datetime import date

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..agents import dossier, legal, memory, taxes
from ..agents.llm import Tool, add_user_text, run_agent
from ..extraction import extract_text
from ..schemas import ChatRequest, ChatResponse, GameState, ToolCall
from ..sessions import Session, game_state, get_session
from ..sim import firm as F
from ..tools import run_tool
from .advisor import _context, calls_since, event_payload, open_event
from .onboarding import llm_enabled

router = APIRouter(prefix="/api/business", tags=["business"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MOCK_REPLY = "Ideea pare viabilă dacă poți acoperi 6 luni de costuri fixe. Hai să vedem un plan de finanțare."

class BusinessChatResponse(ChatResponse):
    state: GameState | None = None


ACCOUNTANT = """Ești contabilul AI din clădirea „Afacere” din Raiff Quest (joc educațional Raiffeisen Bank).
Ești separat de AIngel și de consultantul de investiții. Ajuți utilizatorul să-și deschidă și să-și administreze o mică afacere în România, în anul fiscal 2026.

Ce faci:
- Afli ideea de afacere, veniturile și cheltuielile estimate, dacă ar avea angajați, de ce capital are nevoie.
- Calculezi taxele DOAR cu compare_tax_regimes și calculate_taxes (nu calcula de cap). Explică simplu cât plătește și cât îi rămâne lunar.
- Termene: folosește fiscal_calendar pentru datele concrete (D100, D112, Declarația unică, bilanț, D101) și explică ce se întâmplă la întârziere.
- Legislație: pentru orice regulă, caută cu search_legislation și citează articolul („Codul fiscal, art. 25 alin. (3)”). Nu inventa articole; dacă nu găsești, spune că trebuie verificat.
- Dosarul ONRC: când utilizatorul încarcă documente de înființare, apelează review_dossier și explică ce e complet, ce e doar menționat dar neîncărcat și ce lipsește. Verifică dacă denumirea, sediul, asociatul și codul CAEN sunt aceleași în toate documentele.
- Facturi de cheltuieli: identifică fiecare poziție, alege categoria și apelează classify_expense pentru fiecare poziție importantă. Spune ce e deductibil, în ce procent și ce economie de impozit aduce. La micro, cheltuielile nu reduc impozitul de 1%.
- Când primești <document>, spune întâi pe scurt ce tip de document e și cifrele cheie, apoi aplică regulile de mai sus.
- Ține cont de situația lui personală (get_financial_state) și de fișa comună: dacă afacerea îi pune în pericol bugetul sau scopul, spune-o.
- Când utilizatorul vrea să pornească afacerea în joc, confirmă cifrele și apelează apply_business_to_game. Costul inițial se scade din bani, încasările intră lunar, iar taxele se plătesc la termenele care apar la Afacere. Dacă amână, plătește dobânzi, penalități și amendă.
- {memory_rule}
- Răspunsuri în română, clare, cu liste scurte, maximum ~200 de cuvinte, cu cifrele principale în lei.
- Ești un asistent educațional: încheie calculele importante cu nota că sunt orientative și trebuie verificate cu un expert contabil.

Profilul utilizatorului: {profile}
Documente încărcate până acum: {documents}

{memory}
"""


def _tools(session: Session) -> list[Tool]:
    num = {"type": "number"}
    regime = {"type": "string", "enum": ["pfa", "micro", "profit"]}
    form = {"type": "string", "enum": ["PFA", "SRL"]}
    owner = {"type": "boolean", "description": "la SRL: proprietarul e angajat cu salariul minim (implicit da)"}

    def state():
        view = _context(session)
        if session.sim is not None:
            played = game_state(session).model_dump(mode="json")
            view["joc"] = {
                "luna": played["month"], "solduri": played["balance"], "lunar": played["monthly"],
                "scop": played["goal"], "firma": played.get("firm"),
                "eveniment_deschis": event_payload(open_event(session)),
            }
            view["summary"] = "Situația personală din oraș, inclusiv firma dacă a fost pornită de contabil."
        else:
            view["summary"] = "Jocul nu a pornit încă; am doar profilul."
        return view

    def apply_business_to_game(name: str, form: str, regime: str, startup_cost: float,
                               monthly_revenue: float, monthly_expenses: float, owner_is_employee: bool = True,
                               d112_quarterly: bool = True):
        if session.sim is None:
            return {"error": "Jocul nu a pornit încă.", "summary": "Jocul nu a pornit încă."}
        if session.sim.get("firm"):
            current = session.sim["firm"]["name"]
            return {"error": f"Ai deja o afacere activă: {current}.", "summary": f"Ai deja o afacere activă: {current}."}
        chosen = "pfa" if form.upper() == "PFA" else regime
        result = taxes.calculate(chosen, monthly_revenue * 12, monthly_expenses * 12, owner_is_employee)
        monthly_taxes = round(result["total_taxe"] / 12, 2)
        business = {
            "name": name, "form": form.upper(), "regime": chosen, "regime_label": result["denumire"],
            "startup_cost": float(startup_cost), "monthly_revenue": float(monthly_revenue),
            "monthly_expenses": float(monthly_expenses), "monthly_taxes": monthly_taxes,
            "monthly_net": result["bani_in_mana_lunar"],
            "monthly_cash": round(result["bani_in_mana_lunar"] + monthly_taxes, 2),
            "obligations": taxes.obligations(chosen, result, d112_quarterly),
        }
        F.open_business(session.sim, business)
        memory.add(session.id, "business", "afacere",
                   f"A pornit în joc „{name}” ({result['denumire']}): venit {monthly_revenue:.0f} lei/lună, "
                   f"net după taxe {result['bani_in_mana_lunar']:.0f} lei/lună.")
        from ..schemas import LogEntry
        session.log.append(LogEntry(
            month=session.month, institution="business",
            text=f"Ai pornit „{name}” ({form.upper()}, {result['denumire']}). Cost inițial {startup_cost:.0f} lei.",
        ))
        started = session.sim["firm"]
        return {
            "ok": True, "afacere": {k: started[k] for k in ("name", "form", "regime_label", "monthly_revenue",
                                                           "monthly_expenses", "monthly_taxes", "monthly_cash")},
            "summary": (f"„{name}” pornită în oraș: cost inițial {startup_cost:.0f} lei, "
                        f"{started['monthly_cash']:.0f} lei/lună înainte de taxe, "
                        f"taxe de {monthly_taxes:.0f} lei/lună plătite la termen, la Afacere."),
        }

    return [
        Tool("compare_tax_regimes", "Compară PFA, SRL micro 1% și SRL impozit pe profit, pe sume ANUALE în lei, regulile din 2026.",
             {"type": "object", "properties": {"annual_revenue": num, "annual_expenses": num, "owner_is_employee": owner},
              "required": ["annual_revenue", "annual_expenses"]}, taxes.compare),
        Tool("calculate_taxes", "Calculul detaliat pentru un singur regim, pe sume ANUALE în lei.",
             {"type": "object", "properties": {"regime": regime, "annual_revenue": num, "annual_expenses": num,
                                               "owner_is_employee": owner},
              "required": ["regime", "annual_revenue", "annual_expenses"]}, taxes.calculate),
        Tool("fiscal_calendar", "Termenele fiscale concrete (date) din următoarele luni pentru forma și regimul ales.",
             {"type": "object", "properties": {"form": form, "regime": regime, "has_salaried": {"type": "boolean"},
                                               "vat_payer": {"type": "boolean"}, "d112_quarterly": {"type": "boolean"},
                                               "months": {"type": "integer"}},
              "required": ["form"]}, lambda **kwargs: _calendar(session, **kwargs)),
        Tool("search_legislation", "Caută în textul oficial consolidat al Codului fiscal, Codului de procedură fiscală și Legii 265/2022.",
             {"type": "object", "properties": {"query": {"type": "string"}, "law": {"type": "string", "enum": list(legal.LAWS)},
                                               "article": {"type": "string"}},
              "required": ["query"]}, lambda query, law=None, article=None: legal.search(query, law, article)),
        Tool("review_dossier", "Verifică documentele încărcate pentru dosarul de înființare ONRC (PFA sau SRL).",
             {"type": "object", "properties": {"form": form}, "required": ["form"]},
             lambda form: dossier.review(form, session.business_documents)),
        Tool("classify_expense", "Deductibilitatea unei cheltuieli: procent, sumă deductibilă, economie de impozit, regula legală.",
             {"type": "object", "properties": {
                 "category": {"type": "string", "enum": taxes.EXPENSE_CATEGORIES},
                 "amount": num, "regime": regime, "vat_payer": {"type": "boolean"},
                 "business_share": {"type": "number"}},
              "required": ["category", "amount", "regime"]}, taxes.classify_expense),
        Tool("startup_checklist", "Pașii, documentele și costurile orientative pentru înființarea unui PFA sau SRL.",
             {"type": "object", "properties": {"form": form}, "required": ["form"]}, taxes.checklist),
        Tool("get_financial_state", "Situația financiară personală curentă a utilizatorului din joc, inclusiv firma pornită.",
             {"type": "object", "properties": {}}, state),
        Tool("apply_business_to_game", "Pornește afacerea în oraș: cheltuie costul inițial, adaugă lunar încasările și programează taxele la termene.",
             {"type": "object", "properties": {
                 "name": {"type": "string"}, "form": form, "regime": regime,
                 "startup_cost": num, "monthly_revenue": num, "monthly_expenses": num,
                 "owner_is_employee": owner, "d112_quarterly": {"type": "boolean"}},
              "required": ["name", "form", "regime", "startup_cost", "monthly_revenue", "monthly_expenses"]},
             apply_business_to_game),
        memory.tool(session.id, "business"),
    ]


def _calendar(session: Session, form: str, regime: str = "micro", has_salaried: bool = True,
              vat_payer: bool = False, d112_quarterly: bool = True, months: int = 12) -> dict:
    if session.sim is not None and session.sim.get("calendar_start"):
        year, month = F.calendar(session.sim, session.month + 1)
    else:
        today = date.today()
        year, month = today.year, today.month
    result = taxes.fiscal_calendar(form, regime, year, month, min(max(int(months or 12), 1), 24),
                                   has_salaried, vat_payer, d112_quarterly)
    if isinstance(result, dict) and "summary" not in result:
        result["summary"] = f"Calendar fiscal {form}, {len(result.get('termene', []))} termene."
    return result


def _accountant_system(session: Session) -> str:
    profile = session.profile.model_dump(mode="json") if session.profile else session.agent_profile.get("data", {})
    docs = ", ".join(
        f"{doc['name']} ({', '.join(doc.get('kinds', [])) or 'tip nedetectat'})" for doc in session.business_documents
    ) or "niciunul"
    return ACCOUNTANT.format(
        profile=json.dumps(profile, ensure_ascii=False), documents=docs,
        memory=memory.prompt_block(session.id), memory_rule=memory.RULE,
    ) + "\nContext curent (JSON):\n" + json.dumps(_context(session), ensure_ascii=False)


def _store_document(session: Session, filename: str, data: bytes) -> str:
    try:
        extracted, method = extract_text(filename or "document", data)
    except Exception:
        return f"\n\nFișierul {filename} nu a putut fi citit."
    text = extracted[:15000]
    kinds = dossier.classify(text)
    session.business_documents.append({"name": filename, "kinds": kinds, "text": text, "method": method})
    memory.add(session.id, "business", "documente",
               f"A încărcat la contabil „{filename}”" + (f" ({', '.join(kinds)})" if kinds else "") + ".")
    detected = ", ".join(kinds) or "necunoscut"
    return (f"\n\n<document nume=\"{filename}\" metoda_extragere=\"{method}\" tip_detectat=\"{detected}\">\n"
            f"{text}\n</document>")


def _with_state(session: Session, response: ChatResponse) -> BusinessChatResponse:
    state = game_state(session) if session.sim is not None and session.profile is not None else None
    return BusinessChatResponse(reply=response.reply, tool_calls=response.tool_calls, state=state)


def _live_accountant(session: Session, text: str) -> ChatResponse:
    history = list(session.business_history)
    add_user_text(history, text[:20000])
    try:
        result = run_agent(_accountant_system(session), history, _tools(session), max_tokens=2000)
    except Exception:
        raise HTTPException(502, "Contabilul nu a putut răspunde. Te rugăm să reîncerci.") from None
    session.business_history = history
    calls = [ToolCall(**call) for call in result["tool_calls"]]
    reply = result["text"] or "Nu am putut încheia calculul. Spune-mi venitul și cheltuielile anuale."
    return ChatResponse(reply=reply, tool_calls=calls)


def _mock(session: Session, filename: str | None = None, size: int = 0) -> ChatResponse:
    start = len(session.tool_log)
    run_tool("search_products", {"category": "credit"}, session.id)
    run_tool("compare_products", {"ids": ["credit_nevoi"], "amount": 20000, "months": 36}, session.id)
    tool_calls = calls_since(session, start)
    if filename is not None:
        tool_calls.insert(0, ToolCall(name="read_document", args={"filename": filename},
                                      summary=f"Document primit ({size} octeți), analiză mock."))
    return ChatResponse(reply=MOCK_REPLY, tool_calls=tool_calls)


@router.post("/chat", response_model=BusinessChatResponse)
def business_chat(req: ChatRequest):
    session = get_session(req.session_id)
    if not llm_enabled():
        reply = ChatResponse(
            reply="Sunt contabilul de la Afacere. Spune-mi venitul și cheltuielile anuale și compar PFA cu SRL micro. Poți încărca dosarul sau o factură, iar după ce confirmi cifrele pornesc firma în oraș. Cifrele pentru 2026 sunt orientative.",
            tool_calls=[],
        )
        return _with_state(session, reply)
    return _with_state(session, _live_accountant(session, req.text))


@router.post("/document", response_model=BusinessChatResponse)
async def business_document(session_id: str = Form(...), file: UploadFile = File(...), note: str = Form("")):
    session = get_session(session_id)
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Fișierul depășește 25 MB.")
    if not data:
        raise HTTPException(400, "Fișierul este gol.")
    filename = file.filename or "document"
    if not llm_enabled():
        return _with_state(session, _mock(session, filename, len(data)))
    attachment = _store_document(session, filename, data)
    question = note.strip()[:2000] or "Analizează acest document ca un contabil și spune-mi ce înseamnă pentru afacerea mea."
    return _with_state(session, _live_accountant(session, question + attachment))


@router.post("/message", response_model=BusinessChatResponse)
async def business_message(
    session_id: str = Form(...),
    text: str = Form(...),
    file: UploadFile | None = File(None),
):
    session = get_session(session_id)
    attachment = ""
    filename = None
    size = 0
    if file is not None:
        data = await file.read()
        size = len(data)
        if size > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Fișierul depășește 25 MB.")
        filename = file.filename or ""
        if llm_enabled():
            attachment = _store_document(session, filename or "document", data)
    if not llm_enabled():
        return _with_state(session, _mock(session, filename, size))
    return _with_state(session, _live_accountant(session, text + attachment))
