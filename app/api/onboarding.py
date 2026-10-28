import copy
import logging
import os
from pathlib import Path

import anthropic
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError

from ..agents import onboarding as agent
from ..agents import profile as prof
from ..agents.llm import drain
from ..analyzer import AnalysisError, analyze_statement
from ..extraction import extract_text
from ..statement_spend import summarize
from ..game_profile import to_game_profile
from ..mock_data import ANDREI_PROFILE
from ..profile_mapping import agent_profile_to_profile, missing_fields
from ..schemas import OnboardingMessageRequest, OnboardingMessageResponse, Profile, StatementResponse
from ..sessions import Session, get_session

log = logging.getLogger("extras.onboarding")
router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
SAMPLE_PDF = Path(__file__).resolve().parents[2] / "static" / "demo" / "extras_student.pdf"
SAMPLE_TXT = Path(__file__).resolve().parents[2] / "data" / "extras_student.txt"
MAX_MESSAGE_CHARS = 4000
MOCK_MESSAGES_TO_DONE = 3
MOCK_REPLIES = [
    "Salut! Ce obiectiv financiar ai pentru următorii ani?",
    "Super. Cât câștigi pe lună și cât dai pe chirie, utilități și alte cheltuieli fixe?",
    "Ai economii sau credite în curs? Și cât de confortabil ești cu riscul?",
]
# Mock analysis shaped like deploy/sample_statement.py's synthetic statement.
MOCK_ANALYSIS = {
    "mock": True, "titular": "ION POPESCU", "perioada": {"de_la": "2026-09-01", "pana_la": "2026-09-30"},
    "sold_final": 5309.81, "venit_lunar_estimat": 6850.0, "economii_identificate": 0.0,
    "obligatii_recurente": [
        {"descriere": "Rata credit ipotecar BT", "tip": "rata credit", "suma_lunara": 2310.0},
        {"descriere": "Credius IFN rata", "tip": "rata credit", "suma_lunara": 650.0},
    ],
    "scor_stabilitate_financiara": 58, "nivel_risc": "mediu",
    "semnale_de_risc": ["Rată la IFN", "Pariuri online"],
}


def llm_enabled() -> bool:
    """Real agents only with an API key and MOCK_LLM not set to true (tests and offline demo use the mock)."""
    return bool(os.getenv("ANTHROPIC_API_KEY")) and os.getenv("MOCK_LLM", "").lower() != "true"


def _statement_summary(analysis: dict) -> dict:
    """What the profile keeps from a statement (§4.1 source); never the file or its text."""
    return {"score": analysis.get("scor_stabilitate_financiara"), "risk_signals": (analysis.get("semnale_de_risc") or [])[:4]}


def _complete(session: Session, done: bool) -> tuple[bool, list[str]]:
    """When the agent finished, validate the mapped profile against §4.1 and store it for /api/game/start."""
    if not done:
        return False, missing_fields(session.agent_profile)
    try:
        session.profile = Profile.model_validate(agent_profile_to_profile(session.agent_profile["data"], session.statement))
    except ValidationError as exc:
        log.warning("Onboarding finished but the profile isn't a valid §4.1 profile: %d errors", exc.error_count())
        session.onboarding_convo["done"] = False
        return False, [".".join(str(p) for p in err["loc"]) for err in exc.errors()]
    return True, []


@router.post("/message", response_model=OnboardingMessageResponse)
def onboarding_message(req: OnboardingMessageRequest):
    session = get_session(req.session_id)
    if not llm_enabled():
        return _mock_message(session)

    # Work on copies and commit only if the whole agent turn succeeds (same as app/demo/routes.py).
    draft, convo = copy.deepcopy(session.agent_profile), copy.deepcopy(session.onboarding_convo)
    try:
        result = drain(agent.user_turn(session.id, draft, convo, req.text.strip()[:MAX_MESSAGE_CHARS]))
    except anthropic.APIError as exc:
        log.exception("Onboarding agent call failed")
        raise HTTPException(502, f"Eroare la apelul Claude: {exc}")
    session.agent_profile, session.onboarding_convo = draft, convo
    done, missing = _complete(session, bool(convo["done"]))
    return OnboardingMessageResponse(reply=result["text"], missing_fields=missing, done=done,
                                     profile=session.profile if done else None)


def _mock_message(session: Session) -> OnboardingMessageResponse:
    session.onboarding_messages += 1
    n = session.onboarding_messages
    if n >= MOCK_MESSAGES_TO_DONE:
        session.profile = ANDREI_PROFILE.model_copy(deep=True)
        return OnboardingMessageResponse(
            reply="Mulțumesc, am tot ce-mi trebuie. Hai să începem jocul!",
            missing_fields=[], done=True, profile=session.profile,
        )
    required = missing_fields(session.agent_profile)  # already filled by a statement upload, if any
    collected = len(required) * n // MOCK_MESSAGES_TO_DONE
    return OnboardingMessageResponse(reply=MOCK_REPLIES[n], missing_fields=required[collected:], done=False)


@router.post("/statement", response_model=StatementResponse)
async def onboarding_statement(session_id: str = Form(...), file: UploadFile = File(...)):
    session = get_session(session_id)
    # Read into memory only; uploads are never written to disk.
    data = await file.read()
    if not data:
        raise HTTPException(400, "Fișierul este gol.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Fișierul depășește 25 MB.")
    filename = file.filename or "extras"

    if not llm_enabled():
        del data
        analysis, reply = MOCK_ANALYSIS, None
        patch = agent.statement_patch(analysis, to_game_profile(analysis))
        prof.merge(session.agent_profile, patch, "extras")
        session.statement = _statement_summary(analysis)
    else:
        analysis, patch, reply = await _real_statement(session, filename, data)

    return StatementResponse(
        analysis=analysis,
        profile_fields=agent_profile_to_profile(patch, session.statement),
        missing_fields=missing_fields(session.agent_profile),
        reply=reply,
    )


@router.post("/sample", response_model=StatementResponse)
async def onboarding_sample(session_id: str = Form(...)):
    """The fictional 12-month student statement, so the new frontend can start without a file picker."""
    session = get_session(session_id)
    if not llm_enabled():
        return _sample_from_text(session)
    if not SAMPLE_PDF.is_file():
        raise HTTPException(404, "Extrasul de student nu este pe server.")
    analysis, patch, reply = await _real_statement(session, "extras_student_matei.pdf", SAMPLE_PDF.read_bytes())
    return StatementResponse(
        analysis=analysis,
        profile_fields=agent_profile_to_profile(patch, session.statement),
        missing_fields=missing_fields(session.agent_profile),
        reply=reply,
    )


def _sample_from_text(session: Session) -> StatementResponse:
    stats = summarize(SAMPLE_TXT.read_text(encoding="utf-8"))
    if not stats:
        raise HTTPException(500, "Extrasul de student nu a putut fi citit.")
    analysis = {
        "mock": True, "titular": stats["titular"], "sold_final": stats["sold_final"],
        "venit_lunar_estimat": stats["venit_mediu"], "economii_identificate": 0,
        "medii_lunare": stats["categorii"], "luni_analizate": stats["luni"],
        "cheltuieli_lunare_estimate": stats["cheltuieli_medii"],
        "profil_din_extras": {"varsta": stats["varsta"], "ocupatie": stats["ocupatie"],
                              "locuinta": stats["locuinta"], "alte_intrari_medii": stats["alte_intrari_medii"]},
        "scor_stabilitate_financiara": 35, "nivel_risc": "ridicat", "semnale_de_risc": stats["semnale"],
        "rezumat": "Student, part-time, stă cu părinții. Uber, restaurante, pariuri și rate depășesc venitul.",
    }
    patch = agent.statement_patch(analysis, to_game_profile(analysis))
    prof.merge(session.agent_profile, patch, "extras")
    session.statement = _statement_summary(analysis)
    listed = ", ".join(f"{c['label']} {c['medie_lunara']:.0f} lei" for c in stats["categorii"][:4])
    return StatementResponse(
        analysis=analysis,
        profile_fields=agent_profile_to_profile(patch, session.statement),
        missing_fields=missing_fields(session.agent_profile),
        reply=f"Am citit extrasul de student, pe {stats['luni']} luni. Medii: {listed}.",
    )


async def _real_statement(session: Session, filename: str, data: bytes) -> tuple[dict, dict, str]:
    """Same pipeline as /api/analyze, in memory: extract_text -> analyze_statement -> to_game_profile,
    then the onboarding agent merges the confident fields into the draft profile and replies."""
    try:
        text, _method = await run_in_threadpool(extract_text, filename, data)
    except ValueError as exc:
        raise HTTPException(415, str(exc))
    except Exception:
        log.exception("Extraction failed")
        raise HTTPException(422, "Nu am putut extrage textul din document.")
    if len(text.strip()) < 30:
        raise HTTPException(422, "Documentul nu conține text lizibil (nici după OCR).")

    try:
        analysis = await run_in_threadpool(analyze_statement, text)
    except AnalysisError as exc:
        raise HTTPException(502, str(exc))
    except Exception as exc:
        log.exception("Statement analysis failed")
        raise HTTPException(502, f"Eroare la apelul Claude: {exc}")
    game_profile = to_game_profile(analysis)

    draft, convo = copy.deepcopy(session.agent_profile), copy.deepcopy(session.onboarding_convo)
    try:
        # statement_turn merges agent.statement_patch(...) into `draft` itself, then the agent replies.
        result = await run_in_threadpool(
            lambda: drain(agent.statement_turn(session.id, draft, convo, filename, analysis, game_profile)))
    except anthropic.APIError as exc:
        log.exception("Onboarding agent call failed")
        raise HTTPException(502, f"Eroare la apelul Claude: {exc}")
    session.agent_profile, session.onboarding_convo = draft, convo
    session.statement = _statement_summary(analysis)
    return analysis, agent.statement_patch(analysis, game_profile), result["text"]
