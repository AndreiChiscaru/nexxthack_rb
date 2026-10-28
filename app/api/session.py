from fastapi import APIRouter

from ..schemas import SessionResponse
from ..sessions import create_session

router = APIRouter(prefix="/api", tags=["session"])


@router.post("/session", response_model=SessionResponse)
def new_session():
    return SessionResponse(session_id=create_session().id)
