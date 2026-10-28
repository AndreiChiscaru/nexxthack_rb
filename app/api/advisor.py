from fastapi import APIRouter

from ..schemas import ChatRequest, ChatResponse, ToolCall
from ..sessions import get_session

router = APIRouter(prefix="/api/advisor", tags=["advisor"])


@router.post("/message", response_model=ChatResponse)
def advisor_message(req: ChatRequest):
    # TODO(real): advisor agent (app/agents/) with tools backed by app/sim/engine.py; log every tool call.
    session = get_session(req.session_id)
    s = session.state
    cash = s.balance.cash if s else 0
    tool_calls = [
        ToolCall(name="get_player_profile", args={},
                 summary=f"Luna {s.month if s else 0}, cash {cash:.0f} lei, stres {s.wellbeing.stress if s else 0:.0f}/100."),
        ToolCall(name="search_products", args={"category": "savings"},
                 summary="2 produse demo: Cont de Economii Automat Demo, Depozit Flexibil Demo."),
    ]
    if "credit" in req.text.lower() or "rate" in req.text.lower():
        tool_calls.append(ToolCall(
            name="simulate_decision", args={"option": "A", "months": 36},
            summary="Varianta A: dobândă totală plătită 2.310 lei, rată 650 lei/lună.",
        ))
    return ChatResponse(
        reply="Îți recomand să pui întâi deoparte un fond de urgență de 3 luni, apoi să accelerezi plata creditului.",
        tool_calls=tool_calls,
    )
