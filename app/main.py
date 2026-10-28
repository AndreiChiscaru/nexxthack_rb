import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, File, HTTPException, UploadFile  # noqa: E402
from fastapi.concurrency import run_in_threadpool  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from .agents.llm import AGENT_MODEL  # noqa: E402
from .analyzer import MODEL, AnalysisError, analyze_statement  # noqa: E402
from .api import advisor, business, game, onboarding, products, session  # noqa: E402
from .demo.routes import router as demo_router  # noqa: E402
from .extraction import extract_text  # noqa: E402
from .game_profile import to_game_profile  # noqa: E402

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("extras")

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
GAME_DIR = Path(__file__).resolve().parent.parent / "game"

app = FastAPI(title="Raiff Quest API")
# TODO(deploy): restrict CORS to our domain
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
for module in (session, onboarding, game, advisor, business, products):
    app.include_router(module.router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
if GAME_DIR.is_dir():
    app.mount("/joc", StaticFiles(directory=GAME_DIR, html=True), name="joc")
app.include_router(demo_router)


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/demo")
def demo():
    return FileResponse(STATIC_DIR / "demo" / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "model": MODEL, "agent_model": AGENT_MODEL,
            "agent_mode": "live" if onboarding.llm_enabled() else "mock"}


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):
    data = await file.read()
    if not data:
        raise HTTPException(400, "Fișierul este gol.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Fișierul depășește 25 MB.")

    try:
        text, method = await run_in_threadpool(extract_text, file.filename or "", data)
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
        log.exception("Claude call failed")
        raise HTTPException(502, f"Eroare la apelul Claude: {exc}")

    return {
        "filename": file.filename,
        "extraction_method": method,
        "chars_extracted": len(text),
        "text_preview": text[:3000],
        "analysis": analysis,
        "game_profile": to_game_profile(analysis),
    }
