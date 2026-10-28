"""In-memory session store. Lost on restart; nothing is written to disk."""
# TODO(real): SQLite (or keep in-memory) with TTL eviction so old sessions don't pile up.
import random
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from .schemas import Event, GameState, LogEntry, Profile
from .sim import adapter
from .sim.engine import SimState


@dataclass
class Session:
    id: str
    onboarding_messages: int = 0
    profile: Profile | None = None
    # Engine state is the source of truth; GameState is rebuilt from it on every request.
    sim: SimState | None = None
    rng: random.Random | None = None
    month: int = 0
    year_rep: dict[str, Any] = field(default_factory=dict)
    log: list[LogEntry] = field(default_factory=list)
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


def require_game(session: Session) -> SimState:
    if session.sim is None or session.profile is None:
        raise HTTPException(409, "Jocul nu a pornit încă (POST /api/game/start).")
    return session.sim


def game_state(session: Session) -> GameState:
    sim = require_game(session)
    return adapter.to_game_state(session.id, sim, session.profile, session.month,
                                 session.pending_events, session.log)
