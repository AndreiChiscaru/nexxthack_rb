"""The accountant can start a firm in the city, and tax deadlines become choices at Afacere."""
import pytest
from fastapi.testclient import TestClient

from app.agents import taxes
from app.api.business import _tools
from app.main import app
from app.sessions import get_session

client = TestClient(app)


def _started() -> str:
    sid = client.post("/api/session").json()["session_id"]
    assert client.post("/api/game/start", json={"session_id": sid}).status_code == 200
    return sid


def _start_pfa(sid: str):
    session = get_session(sid)
    tool = next(item for item in _tools(session) if item.name == "apply_business_to_game")
    result = tool.handler(name="Studio web", form="PFA", regime="pfa", startup_cost=500,
                          monthly_revenue=2000, monthly_expenses=500)
    assert result["ok"] is True
    return session, taxes.calculate("pfa", 2000 * 12, 500 * 12)


def test_accountant_tools_cover_documents_and_starting_the_firm():
    names = {tool.name for tool in _tools(get_session(_started()))}
    assert {"review_dossier", "classify_expense", "apply_business_to_game", "search_legislation"} <= names


def test_starting_a_firm_spends_cash_and_shows_it_in_the_city():
    sid = _started()
    session, _calc = _start_pfa(sid)
    state = client.get("/api/game/state", params={"session_id": sid}).json()
    assert state["firm"]["name"] == "Studio web"
    assert state["firm"]["form"] == "PFA"
    assert state["balance"]["cash"] == pytest.approx(4000 - 500)
    assert state["monthly"]["income"] == pytest.approx(4300 + 2000)
    assert state["monthly"]["expenses"]["business"] == pytest.approx(500)
    again = next(item for item in _tools(session) if item.name == "apply_business_to_game")
    assert "deja" in again.handler(name="Altă", form="SRL", regime="micro", startup_cost=1,
                                   monthly_revenue=1, monthly_expenses=0)["error"]


def test_may_deadline_must_be_paid_and_a_delay_comes_back_with_extra():
    sid = _started()
    session, calc = _start_pfa(sid)
    session.sim["calendar_start"] = [2026, 4]
    advanced = client.post("/api/game/advance", json={"session_id": sid})
    assert advanced.status_code == 200, advanced.text
    event = advanced.json()["events"][0]
    assert event["id"] == "fiscal_deadline"
    assert "mai 2026" in event["title"]
    due = event["options"][0]["ops"]["fiscal_pay"]
    assert due == pytest.approx(calc["total_taxe"] / 12, abs=0.02)
    assert advanced.json()["state"]["firm"]["taxes_due"] == pytest.approx(due, abs=0.02)
    blocked = client.post("/api/game/advance", json={"session_id": sid})
    assert blocked.status_code == 409

    delayed = client.post("/api/game/action", json={
        "session_id": sid, "institution": "business", "action_id": "fiscal_deadline",
        "params": {"option_id": "aman"},
    })
    assert delayed.status_code == 200, delayed.text
    nxt = client.post("/api/game/advance", json={"session_id": sid}).json()["events"][0]
    assert nxt["id"] == "fiscal_arrears"
    cash = client.get("/api/game/state", params={"session_id": sid}).json()["balance"]["cash"]
    extra = nxt["options"][0]["ops"]["fiscal_pay"]
    assert extra > due
    paid = client.post("/api/game/action", json={
        "session_id": sid, "institution": "business", "action_id": "fiscal_arrears",
        "params": {"option_id": "plateste"},
    })
    assert paid.status_code == 200, paid.text
    assert paid.json()["state"]["balance"]["cash"] == pytest.approx(cash - extra, abs=0.05)
    # The arrears are gone. The month just played has already accrued the next instalment.
    assert paid.json()["state"]["firm"]["taxes_due"] == pytest.approx(due, abs=0.05)


def test_business_document_upload_is_accepted_without_a_live_model(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "true")
    sid = client.post("/api/session").json()["session_id"]
    response = client.post(
        "/api/business/document",
        data={"session_id": sid, "note": "verifică factura"},
        files={"file": ("factura.txt", "Factura\nTotal de plata 100".encode(), "text/plain")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["tool_calls"][0]["name"] == "read_document"
