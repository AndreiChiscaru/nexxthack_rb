"""In-memory session store. Lost on restart; nothing is written to disk."""
# TODO(real): SQLite (or keep in-memory) with TTL eviction so old sessions don't pile up.
import random
from threading import RLock
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from .agents import onboarding as onboarding_agent
from .agents import profile as prof
from .schemas import Event, GameState, LogEntry, Profile
from .sim import adapter
from .sim.engine import SimState


@dataclass
class Session:
    id: str
    lock: Any = field(default_factory=RLock, repr=False, compare=False)
    onboarding_messages: int = 0
    # Full Claude advisor transcript, including tool use/results; volatile and session-scoped.
    advisor_history: list[dict] = field(default_factory=list)
    # Separate transcript for the investment consultant, so it does not overwrite AIngel.
    investment_history: list[dict] = field(default_factory=list)
    # Accountant at the Business building; also separate from AIngel.
    business_history: list[dict] = field(default_factory=list)
    # Documents the accountant has read (name, kinds, text). Not shown in the Godot UI.
    business_documents: list[dict] = field(default_factory=list)
    # Decision the player is looking at, sent with the consultant's question.
    focus_event_id: str | None = None
    # Onboarding agent state, in the agent's own formats (app/agents/): draft profile and conversation.
    agent_profile: dict = field(default_factory=prof.empty)
    onboarding_convo: dict = field(default_factory=onboarding_agent.new_conversation)
    # Only what the profile needs from an uploaded statement ({score, risk_signals}); never the file or its text.
    statement: dict | None = None
    # §4.1 profile, set when onboarding is done; /api/game/start reads it.
    profile: Profile | None = None
    # Engine state is the source of truth; GameState is rebuilt from it on every request.
    sim: SimState | None = None
    rng: random.Random | None = None
    month: int = 0
    year_rep: dict[str, Any] = field(default_factory=dict)
    log: list[LogEntry] = field(default_factory=list)
    pending_events: list[Event] = field(default_factory=list)
    # Statement profiles get cut suggestions instead of the generic event library.
    cut_mode: bool = False
    # institution -> {"cycle": ids used in the current cycle, "last": last id}; see app/sim/events.py schedule().
    used_events: dict[str, dict] = field(default_factory=dict)
    # Every agent tool call ({name, args, summary, duration_ms}); see app/tools.py run_tool().
    tool_log: list[dict] = field(default_factory=list)


_SESSIONS: dict[str, Session] = {}


def create_session() -> Session:
    session = Session(id=uuid4().hex)
    _SESSIONS[session.id] = session
    return session


def find_session(session_id: str) -> Session | None:
    return _SESSIONS.get(session_id)


def get_session(session_id: str) -> Session:
    session = find_session(session_id)
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
