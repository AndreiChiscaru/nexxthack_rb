"""HTTP API for the demo game: sessions, the 4 agents (streamed as server-sent events) and game actions."""
import json
import logging
import random

import anthropic
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..agents import business, consultant, memory, onboarding, store
from ..agents import profile as prof
from ..analyzer import AnalysisError, analyze_statement
from ..extraction import extract_text
from ..game_profile import to_game_profile
from . import engine

log = logging.getLogger("extras.demo")
router = APIRouter(prefix="/api/demo")
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class Message(BaseModel):
    text: str


class Choice(BaseModel):
    option_id: str


class BankAction(BaseModel):
    action: str
    amount: float = 0


def _require(session_id: str) -> None:
    if not store.exists(session_id):
        raise HTTPException(404, "Sesiune inexistentă. Reîncarcă pagina.")


def _chat(convo: dict | None) -> list:
    return convo["display"] if convo else []


def _view(session_id: str) -> dict:
    profile = store.load(session_id, "profile", prof.empty())
    convo = store.load(session_id, "onboarding")
    game = store.load(session_id, "game")
    statement = store.load(session_id, "statement")
    return {
        "session_id": session_id,
        "profile": {"fields": prof.fields_view(profile), "missing": prof.missing(profile)},
        "onboarding": {"chat": _chat(convo), "done": bool(convo and convo["done"]), "scenario": convo and convo["scenario"]},
        "statement": statement and {
            "filename": statement["filename"],
            "score": statement["analysis"].get("scor_stabilitate_financiara"),
            "risk": statement["analysis"].get("nivel_risc"),
            "summary": statement["analysis"].get("rezumat"),
            "months": statement["analysis"].get("luni_analizate"),
            "categories": [{"label": c["label"], "monthly": c["medie_lunara"]}
                           for c in (statement["analysis"].get("medii_lunare") or [])],
        },
        "game": engine.public_view(game) if game else None,
        "consultant": _chat(store.load(session_id, "consultant")),
        "business": _chat(store.load(session_id, "business")),
        "memory": memory.load(session_id),
    }


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"


def _stream(session_id: str, run, save) -> StreamingResponse:
    """`run()` yields agent events; `save()` persists the mutated state, only if the whole turn succeeded."""
    def generate():
        try:
            for event in run():
                if event["type"] in ("text", "tool_start", "tool_end", "status"):
                    yield _sse(event)
            save()
            yield _sse({"type": "view", "view": _view(session_id)})
        except (AnalysisError, ValueError) as exc:
            yield _sse({"type": "error", "message": str(exc)})
        except anthropic.APIError as exc:
            log.exception("Claude call failed")
            yield _sse({"type": "error", "message": f"Eroare la apelul Claude: {exc}"})
        except Exception as exc:
            log.exception("Agent turn failed")
            yield _sse({"type": "error", "message": f"Eroare internă: {exc}"})

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


async def _read_upload(file: UploadFile) -> bytes:
    data = await file.read()
    if not data:
        raise HTTPException(400, "Fișierul este gol.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Fișierul depășește 25 MB.")
    return data


def _extract(filename: str, data: bytes) -> tuple[str, str]:
    text, method = extract_text(filename, data)
    if len(text.strip()) < 30:
        raise ValueError("Documentul nu conține text lizibil (nici după OCR).")
    return text, method


# ---------------------------------------------------------------- sessions

@router.post("/session")
def create_session():
    session_id = store.new_session()
    store.save(session_id, "profile", prof.empty())
    store.save(session_id, "onboarding", onboarding.new_conversation())
    return _view(session_id)


@router.get("/session/{session_id}")
def get_session(session_id: str):
    _require(session_id)
    return _view(session_id)


@router.delete("/session/{session_id}")
def delete_session(session_id: str):
    store.delete(session_id)
    return {"ok": True}


# ---------------------------------------------------------------- agent 1 + 2: onboarding and statement

@router.post("/onboarding/{session_id}/message")
def onboarding_message(session_id: str, body: Message):
    _require(session_id)
    profile = store.load(session_id, "profile", prof.empty())
    convo = store.load(session_id, "onboarding")

    def save():
        store.save(session_id, "profile", profile)
        store.save(session_id, "onboarding", convo)

    return _stream(session_id, lambda: onboarding.user_turn(session_id, profile, convo, body.text.strip()[:4000]), save)


@router.post("/onboarding/{session_id}/statement")
async def onboarding_statement(session_id: str, file: UploadFile = File(...)):
    _require(session_id)
    data = await _read_upload(file)
    filename = file.filename or "extras"
    profile = store.load(session_id, "profile", prof.empty())
    convo = store.load(session_id, "onboarding")

    def run():
        yield {"type": "status", "text": "Citesc documentul (OCR dacă e nevoie)…"}
        text, method = _extract(filename, data)
        yield {"type": "status", "text": "Agentul de analiză extrage datele din extras…"}
        analysis = analyze_statement(text)
        game_profile = to_game_profile(analysis)
        store.save(session_id, "statement", {"filename": filename, "method": method, "analysis": analysis, "game_profile": game_profile})
        yield {"type": "status", "text": "Raportul a ajuns la agentul de onboarding…"}
        yield from onboarding.statement_turn(session_id, profile, convo, filename, analysis, game_profile)

    def save():
        store.save(session_id, "profile", profile)
        store.save(session_id, "onboarding", convo)

    return _stream(session_id, run, save)


# ---------------------------------------------------------------- game

def _load_game(session_id: str) -> dict:
    _require(session_id)
    game = store.load(session_id, "game")
    if not game:
        raise HTTPException(409, "Jocul nu a pornit încă.")
    return game


def _game_op(session_id: str, fn, *args):
    game = _load_game(session_id)
    try:
        fn(game, *args)
    except engine.GameError as exc:
        raise HTTPException(409, str(exc))
    store.save(session_id, "game", game)
    return _view(session_id)


@router.post("/game/{session_id}/start")
def game_start(session_id: str):
    _require(session_id)
    profile = store.load(session_id, "profile", prof.empty())
    missing = prof.missing(profile)
    if missing:
        raise HTTPException(409, "Profil incomplet: lipsesc " + ", ".join(missing))
    store.save(session_id, "game", engine.new_game(profile["data"], random.randint(1, 10**6)))
    store.save(session_id, "consultant", consultant.new_conversation())
    store.save(session_id, "business", business.new_conversation())
    return _view(session_id)


@router.post("/game/{session_id}/advance")
def game_advance(session_id: str):
    return _game_op(session_id, engine.advance)


@router.post("/game/{session_id}/choose")
def game_choose(session_id: str, body: Choice):
    return _game_op(session_id, engine.choose, body.option_id)


@router.post("/game/{session_id}/bank")
def game_bank(session_id: str, body: BankAction):
    return _game_op(session_id, engine.bank_action, body.action, body.amount)


# ---------------------------------------------------------------- agent 3: consultant

@router.post("/consultant/{session_id}/message")
def consultant_message(session_id: str, body: Message):
    _require(session_id)
    convo = store.load(session_id, "consultant") or consultant.new_conversation()
    return _stream(session_id, lambda: consultant.user_turn(session_id, convo, body.text.strip()[:4000]),
                   lambda: store.save(session_id, "consultant", convo))


# ---------------------------------------------------------------- agent 4: business accountant

@router.post("/business/{session_id}/message")
def business_message(session_id: str, body: Message):
    _require(session_id)
    convo = store.load(session_id, "business") or business.new_conversation()
    return _stream(session_id, lambda: business.user_turn(session_id, convo, body.text.strip()[:4000]),
                   lambda: store.save(session_id, "business", convo))


@router.post("/business/{session_id}/document")
async def business_document(session_id: str, file: UploadFile = File(...), note: str = Form("")):
    _require(session_id)
    data = await _read_upload(file)
    filename = file.filename or "document"
    convo = store.load(session_id, "business") or business.new_conversation()

    def run():
        yield {"type": "status", "text": "Citesc documentul (OCR dacă e nevoie)…"}
        text, method = _extract(filename, data)
        yield from business.document_turn(session_id, convo, filename, text, method, note.strip()[:2000])

    return _stream(session_id, run, lambda: store.save(session_id, "business", convo))
