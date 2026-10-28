from fastapi import APIRouter

from ..catalog import catalog_products
from ..schemas import ChatRequest, ChatResponse, ToolCall
from ..sessions import get_session

router = APIRouter(prefix="/api/advisor", tags=["advisor"])


def _search_products(category: str) -> ToolCall:
    """Mock tool call over the real catalog, so names match what the frontend shows from /api/products."""
    found = catalog_products(category)
    return ToolCall(name="search_products", args={"category": category},
                    summary=f"{len(found)} produse ({category}): " + ", ".join(p.name for p in found))


@router.post("/message", response_model=ChatResponse)
def advisor_message(req: ChatRequest):
    # TODO(real): advisor agent (app/agents/) with tools backed by app/sim/engine.py; log every tool call.
    session = get_session(req.session_id)
    sim = session.sim
    cash = sim["cash"] if sim else 0
    stress = sim["stress"] if sim else 0
    tool_calls = [
        ToolCall(name="get_player_profile", args={},
                 summary=f"Luna {session.month}, cash {cash:.0f} lei, stres {stress:.0f}/100."),
        _search_products("economii"),
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
