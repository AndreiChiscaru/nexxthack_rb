from fastapi import APIRouter

from ..schemas import ChatRequest, ChatResponse, ToolCall
from ..sessions import Session, get_session
from ..tools import run_tool

router = APIRouter(prefix="/api/advisor", tags=["advisor"])

CREDIT_WORDS = ("credit", "rate", "împrumut")


def calls_since(session: Session, start: int) -> list[ToolCall]:
    return [ToolCall(**call) for call in session.tool_log[start:]]


@router.post("/message", response_model=ChatResponse)
def advisor_message(req: ChatRequest):
    # TODO(real): the consultant agent with TOOL_SCHEMAS + run_tool, once app/agents/consultant.py accepts
    # external tools (see docs/api.md, "Tools for agents"). Until then: fixed reply, but the tool calls are real.
    session = get_session(req.session_id)
    start = len(session.tool_log)
    game_started = session.sim is not None
    asks_credit = any(word in req.text.lower() for word in CREDIT_WORDS)
    if game_started:
        run_tool("get_goal_progress", {}, session.id)
    run_tool("search_products", {"category": "economii"}, session.id)
    if asks_credit:
        run_tool("compare_products", {"ids": ["credit_nevoi", "refinantare"], "amount": 10000, "months": 36}, session.id)
    elif game_started:
        run_tool("create_action_plan", {}, session.id)
    else:
        run_tool("search_products", {"category": "credit"}, session.id)
    return ChatResponse(
        reply="Îți recomand să pui întâi deoparte un fond de urgență de 3 luni, apoi să accelerezi plata creditului.",
        tool_calls=calls_since(session, start),
    )
