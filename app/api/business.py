from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..schemas import ChatResponse, ToolCall
from ..sessions import get_session
from .advisor import _search_products

router = APIRouter(prefix="/api/business", tags=["business"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024


@router.post("/message", response_model=ChatResponse)
async def business_message(
    session_id: str = Form(...),
    text: str = Form(...),
    file: UploadFile | None = File(None),
):
    get_session(session_id)
    tool_calls = [
        _search_products("credit"),
        ToolCall(name="simulate_decision", args={"principal": 20000, "apr": 0.099, "months": 36},
                 summary="Rată estimată 644 lei/lună, dobândă totală 3.190 lei."),
    ]
    if file is not None:
        # Read into memory only; uploads are never written to disk.
        data = await file.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Fișierul depășește 25 MB.")
        # TODO(real): extract_text(file.filename, data) and pass the text to the business agent.
        tool_calls.insert(0, ToolCall(name="read_document", args={"filename": file.filename or ""},
                                      summary=f"Document primit ({len(data)} octeți), analiză mock."))
        del data
    # TODO(real): business agent (app/agents/) with document reading + engine-backed simulation tools.
    return ChatResponse(
        reply="Ideea pare viabilă dacă poți acoperi 6 luni de costuri fixe. Hai să vedem un plan de finanțare.",
        tool_calls=tool_calls,
    )
