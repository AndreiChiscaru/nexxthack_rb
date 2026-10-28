"""In-memory session store. Lost on restart; nothing is written to disk."""
# TODO(real): SQLite (or keep in-memory) with TTL eviction so old sessions don't pile up.
from dataclasses import dataclass, field
from uuid import uuid4

from fastapi import HTTPException

from .schemas import Event, GameState, Profile


@dataclass
class Session:
    id: str
    onboarding_messages: int = 0
    profile: Profile | None = None
    state: GameState | None = None
    pending_events: list[Event] = field(default_factory=list)


_SESSIONS: dict[str, Session] = {}


def create_session() -> Session:
    session = Session(id=uuid4().hex)
    _SESSIONS[session.id] = session
    return session


def get_session(session_id: str) -> Session:
    session = _SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(404, "Sesiune inexistentă.")
    return session


def get_state(session: Session) -> GameState:
    if session.state is None:
        raise HTTPException(409, "Jocul nu a pornit încă (POST /api/game/start).")
    return session.state
