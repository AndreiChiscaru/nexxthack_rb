import json
from datetime import date

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..agents import legal, taxes
from ..agents.llm import Tool, add_user_text, run_agent
from ..extraction import extract_text
from ..schemas import ChatRequest, ChatResponse, ToolCall
from ..sessions import Session, get_session
from ..tools import run_tool
from .advisor import _context, calls_since
from .onboarding import llm_enabled

router = APIRouter(prefix="/api/business", tags=["business"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MOCK_REPLY = "Ideea pare viabilă dacă poți acoperi 6 luni de costuri fixe. Hai să vedem un plan de finanțare."

ACCOUNTANT = """Ești contabilul AI din clădirea Afacere din Raiff Quest.
Ești separat de AIngel și de consultantul de investiții: tu te ocupi de PFA, SRL, taxe și documente.
Răspunde în română, cu liste scurte, maximum 200 de cuvinte.
Calculează taxele doar cu compare_tax_regimes și calculate_taxes, pe sume anuale. Nu calcula de cap.
Pentru reguli, caută cu search_legislation și citează articolul. Dacă nu găsești textul, spune că trebuie verificat.
Cifrele sunt orientative pentru anul fiscal 2026, simplificate, și trebuie verificate cu un expert contabil.
Nu promite că ai pornit afacerea în joc.
Context curent (JSON):
"""


def _tools(session: Session) -> list[Tool]:
    num = {"type": "number"}
    regime = {"type": "string", "enum": ["pfa", "micro", "profit"]}
    form = {"type": "string", "enum": ["PFA", "SRL"]}

    def state():
        view = _context(session)
        view["summary"] = "Situația personală din joc și profilul de onboarding."
        return view

    return [
        Tool("compare_tax_regimes", "Compară PFA, SRL micro 1% și SRL impozit pe profit, pe sume ANUALE în lei, regulile din 2026.",
             {"type": "object", "properties": {"annual_revenue": num, "annual_expenses": num, "owner_is_employee": {"type": "boolean"}},
              "required": ["annual_revenue", "annual_expenses"]}, taxes.compare),
        Tool("calculate_taxes", "Calculul detaliat pentru un singur regim, pe sume ANUALE în lei.",
             {"type": "object", "properties": {"regime": regime, "annual_revenue": num, "annual_expenses": num,
                                               "owner_is_employee": {"type": "boolean"}},
              "required": ["regime", "annual_revenue", "annual_expenses"]}, taxes.calculate),
        Tool("fiscal_calendar", "Termenele fiscale din următoarele luni pentru PFA sau SRL.",
             {"type": "object", "properties": {"form": form, "regime": regime, "months": {"type": "integer"}},
              "required": ["form"]}, _calendar),
        Tool("search_legislation", "Caută în Codul fiscal, Codul de procedură fiscală și Legea 265/2022.",
             {"type": "object", "properties": {"query": {"type": "string"}, "article": {"type": "string"}},
              "required": ["query"]}, lambda query, article=None: legal.search(query, article=article)),
        Tool("startup_checklist", "Pașii și documentele pentru înființarea unui PFA sau SRL.",
             {"type": "object", "properties": {"form": form}, "required": ["form"]}, taxes.checklist),
        Tool("classify_expense", "Cât dintr-o cheltuială este deductibilă și ce economie de impozit aduce.",
             {"type": "object", "properties": {"category": {"type": "string", "enum": taxes.EXPENSE_CATEGORIES},
                                               "amount": num, "regime": regime},
              "required": ["category", "amount", "regime"]}, taxes.classify_expense),
        Tool("get_financial_state", "Situația personală curentă a utilizatorului.",
             {"type": "object", "properties": {}}, state),
    ]


def _calendar(form: str, regime: str = "micro", months: int = 12) -> dict:
    today = date.today()
    result = taxes.fiscal_calendar(form, regime, today.year, today.month, min(max(months, 1), 24))
    if isinstance(result, dict) and "summary" not in result:
        result["summary"] = f"Calendar fiscal {form}, {len(result.get('termene', result.get('entries', [])))} luni."
    return result


def _live_accountant(session: Session, text: str) -> ChatResponse:
    history = list(session.business_history)
    add_user_text(history, text[:8000])
    try:
        result = run_agent(ACCOUNTANT + json.dumps(_context(session), ensure_ascii=False), history, _tools(session), max_tokens=2000)
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


@router.post("/chat", response_model=ChatResponse)
def business_chat(req: ChatRequest):
    session = get_session(req.session_id)
    if not llm_enabled():
        return ChatResponse(
            reply="Sunt contabilul de la Afacere. Spune-mi venitul și cheltuielile anuale și compar PFA cu SRL micro. Cifrele pentru 2026 sunt orientative.",
            tool_calls=[],
        )
    return _live_accountant(session, req.text)


@router.post("/message", response_model=ChatResponse)
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
            try:
                extracted, method = extract_text(filename or "document", data)
                attachment = f"\n\n<document nume=\"{filename}\" metoda=\"{method}\">\n{extracted[:15000]}\n</document>"
            except Exception:
                attachment = f"\n\nFișierul {filename} nu a putut fi citit."
    if not llm_enabled():
        return _mock(session, filename, size)
    return _live_accountant(session, text + attachment)
