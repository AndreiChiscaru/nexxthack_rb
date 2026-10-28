from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..mock_data import ANDREI_PROFILE, REQUIRED_FIELDS
from ..schemas import OnboardingMessageRequest, OnboardingMessageResponse, StatementResponse
from ..sessions import get_session

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

MOCK_MESSAGES_TO_DONE = 3
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MOCK_REPLIES = [
    "Salut! Ce obiectiv financiar ai pentru următorii ani?",
    "Super. Cât câștigi pe lună și cât dai pe chirie, utilități și alte cheltuieli fixe?",
    "Ai economii sau credite în curs? Și cât de confortabil ești cu riscul?",
]


@router.post("/message", response_model=OnboardingMessageResponse)
def onboarding_message(req: OnboardingMessageRequest):
    # TODO(real): onboarding agent (app/agents/) that extracts fields from req.text and calls submit_profile.
    session = get_session(req.session_id)
    session.onboarding_messages += 1
    n = session.onboarding_messages
    if n >= MOCK_MESSAGES_TO_DONE:
        session.profile = ANDREI_PROFILE.model_copy(deep=True)
        return OnboardingMessageResponse(
            reply="Mulțumesc, am tot ce-mi trebuie. Hai să începem jocul!",
            missing_fields=[], done=True, profile=session.profile,
        )
    collected = len(REQUIRED_FIELDS) * n // MOCK_MESSAGES_TO_DONE
    return OnboardingMessageResponse(
        reply=MOCK_REPLIES[n], missing_fields=REQUIRED_FIELDS[collected:], done=False,
    )


@router.post("/statement", response_model=StatementResponse)
async def onboarding_statement(session_id: str = Form(...), file: UploadFile = File(...)):
    get_session(session_id)
    # Read into memory only; uploads are never written to disk.
    data = await file.read()
    if not data:
        raise HTTPException(400, "Fișierul este gol.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Fișierul depășește 25 MB.")
    del data
    # TODO(real): extract_text + analyze_statement + to_game_profile (same pipeline as /api/analyze),
    # then map the result onto §4.1 profile fields.
    p = ANDREI_PROFILE
    return StatementResponse(
        analysis={"mock": True, "statement_score": 58, "risk_signals": ["Rată la IFN"]},
        profile_fields={
            "income": p.income.model_dump(),
            "recurring": p.recurring.model_dump(),
            "debts": [d.model_dump() for d in p.debts],
            "source": p.source.model_dump(),
        },
        missing_fields=["goal", "age", "savings", "risk_tolerance"],
    )
