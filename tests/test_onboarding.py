"""Onboarding: agent profile -> §4.1 mapping, statement merge, and the real-agent path (agent faked, no network)."""
import ast
import builtins
from pathlib import Path

import anthropic
import httpx
import pymupdf
import pytest
from fastapi.testclient import TestClient

from app import sessions
from app.agents import onboarding as agent
from app.agents import profile as prof
from app.api import onboarding as onboarding_api
from app.extraction import extract_text
from app.game_profile import to_game_profile
from app.main import app
from app.profile_mapping import agent_profile_to_profile, missing_fields
from app.schemas import Profile
from app.sim import adapter

client = TestClient(app)
SAMPLE_STATEMENT = Path(__file__).resolve().parents[1] / "deploy" / "sample_statement.py"

AGENT_DATA = {
    "name": "Andrei", "age": 22, "occupation": "programator junior",
    "goal": {"description": "Avans pentru apartament în Cluj", "type": "avans_casa",
             "target_amount": 25000, "horizon_months": 36},
    "income": {"salary": 4300, "scholarship": 300, "other": 100},
    "home": {"housing": 1500, "utilities": 350, "subscriptions": 120},
    "market": {"food": 1200, "transport": 200, "leisure": 400},
    "education": {"status": "student", "tuition_monthly": 0},
    "health": {"insured": False, "monthly_costs": 80},
    "bank": {"cash": 4000, "savings": 1200, "investments": 0,
             "debts": [{"name": "Credit nevoi personale", "monthly_payment": 650, "remaining": 11000, "apr": 0.14}]},
    "risk_tolerance": "medie", "dependents": 0,
    "business": {"interest": True, "idea": "cafenea mobilă"},
}


def new_session() -> str:
    return client.post("/api/session").json()["session_id"]


# ---------------------------------------------------------------- mapping

def test_mapping_full_agent_profile_validates_as_profile():
    p = Profile.model_validate(agent_profile_to_profile(AGENT_DATA))
    assert (p.name, p.age) == ("Andrei", 22)
    assert p.goal.type == "avans_casa" and p.goal.target_amount == 25000 and p.goal.horizon_months == 36
    assert (p.income.salary, p.income.other) == (4300, 100)
    assert p.education.scholarship == 300
    assert (p.recurring.rent, p.recurring.utilities, p.recurring.subscriptions, p.recurring.transport) == (1500, 350, 120, 200)
    assert (p.spending.food, p.spending.leisure) == (1200, 400)
    assert (p.cash, p.savings, p.investments) == (4000, 1200, 0)
    assert p.debts[0].model_dump() == {"name": "Credit nevoi personale", "monthly": 650, "remaining": 11000, "apr": 0.14}
    assert p.health.insured is False and p.health.monthly_costs == 80
    assert p.business_interest is True
    assert p.risk_tolerance == "medie"


def test_mapping_drops_agent_only_fields():
    out = agent_profile_to_profile(AGENT_DATA)
    assert "occupation" not in out and "business" not in out
    assert "idea" not in str(out)


def test_mapping_defaults_goal_type_and_empty_debts():
    data = {**AGENT_DATA, "goal": {"description": "x", "target_amount": 1000, "horizon_months": 12},
            "bank": {"cash": 1, "savings": 2}}
    out = agent_profile_to_profile(data)
    assert out["goal"]["type"] == "altul"
    assert out["debts"] == []


@pytest.mark.parametrize(("name", "apr", "months"), [
    ("Credit ipotecar BT", 0.065, 240),
    ("Credius IFN", 0.35, 24),
    ("Leasing auto", 0.10, 48),
])
def test_mapping_estimates_missing_apr_and_remaining(name, apr, months):
    [debt] = agent_profile_to_profile({"bank": {"debts": [{"name": name, "monthly_payment": 1000}]}})["debts"]
    assert debt["apr"] == apr
    r = apr / 12
    assert debt["remaining"] == pytest.approx(1000 * (1 - (1 + r) ** -months) / r, abs=0.01)


def test_mapping_zero_apr_without_remaining():
    [debt] = agent_profile_to_profile({"bank": {"debts": [{"name": "Rate magazin", "monthly_payment": 100, "apr": 0}]}})["debts"]
    assert debt["apr"] == 0 and debt["remaining"] == 100 * 48


def test_mapping_statement_source():
    out = agent_profile_to_profile({}, {"score": 58, "risk_signals": ["Rată la IFN"]})
    assert out["source"] == {"statement_uploaded": True, "statement_score": 58, "risk_signals": ["Rată la IFN"]}


def test_missing_fields_are_profile_paths():
    assert missing_fields(prof.empty()) == [
        "name", "age", "occupation", "goal.description", "goal.target_amount", "goal.horizon_months",
        "income.salary", "recurring.rent", "recurring.utilities", "spending.food", "cash", "savings", "risk_tolerance"]
    assert missing_fields({"data": AGENT_DATA, "sources": {}}) == []


def test_scholarship_and_health_costs_reach_the_engine():
    p = Profile.model_validate(agent_profile_to_profile(AGENT_DATA))
    sim, _ = adapter.profile_to_state(p, "x")
    assert sim["side_income"] == 100 + 300
    assert sim["living"] == 1500 + 350 + 120 + 200 + 1200 + 400 + 80
    ex = adapter.expenses(sim, p)
    assert ex.health == 80
    assert sum(ex.model_dump().values()) == pytest.approx(sim["living"] + 650)


# ---------------------------------------------------------------- statement merge (deploy/sample_statement.py data)

def _sample_rows() -> list[tuple]:
    """ROWS from deploy/sample_statement.py, read without importing it (importing would save a PDF to disk)."""
    tree = ast.parse(SAMPLE_STATEMENT.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == "ROWS")
    return ast.literal_eval(node.value)


def _sample_pdf_bytes() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    y = 60
    for line in ["BANCA TRANSILVANIA - EXTRAS DE CONT", "Titular: Ion Popescu", "Perioada: 01.09.2026 - 30.09.2026", ""]:
        page.insert_text((40, y), line, fontsize=11)
        y += 18
    for date, desc, amount, balance in _sample_rows():
        page.insert_text((40, y), f"{date}  {desc}  {amount}  {balance}", fontsize=9)
        y += 15
    return doc.tobytes()


# What the analysis agent returns for that statement (fixed here: tests don't call Claude).
SAMPLE_ANALYSIS = {
    "titular": "ION POPESCU", "perioada": {"de_la": "2026-09-01", "pana_la": "2026-09-30"},
    "sold_final": 5309.81, "venit_lunar_estimat": 6850.0, "economii_identificate": 0.0,
    "obligatii_recurente": [
        {"descriere": "Rata credit ipotecar BT", "tip": "rata credit", "suma_lunara": 2310.0},
        {"descriere": "Credius IFN rata", "tip": "rata credit", "suma_lunara": 650.0},
    ],
    "scor_stabilitate_financiara": 58, "nivel_risc": "mediu", "semnale_de_risc": ["Rată la IFN", "Pariuri online"],
}


def test_sample_statement_text_extracts_in_memory():
    text, method = extract_text("extras.pdf", _sample_pdf_bytes())
    assert "Ion Popescu" in text and "6.850,00" in text and "5.309,81" in text
    assert method


def test_statement_merge_fills_draft_so_agent_stops_asking():
    draft = prof.empty()
    before = missing_fields(draft)
    prof.merge(draft, agent.statement_patch(SAMPLE_ANALYSIS, to_game_profile(SAMPLE_ANALYSIS)), "extras")
    after = missing_fields(draft)
    for path in ("name", "income.salary", "cash", "savings"):
        assert path in before and path not in after
    mapped = agent_profile_to_profile(draft["data"])
    assert mapped["name"] == "Ion Popescu"
    assert mapped["income"]["salary"] == 6850 and mapped["cash"] == 5309.81
    assert [(d["name"], d["monthly"], d["apr"]) for d in mapped["debts"]] == [
        ("Rata credit ipotecar BT", 2310.0, 0.065), ("Credius IFN rata", 650.0, 0.35)]


def test_statement_endpoint_merges_and_writes_nothing(monkeypatch):
    sid = new_session()
    real_open = builtins.open

    def no_writes(file, mode="r", *args, **kwargs):
        assert not any(m in mode for m in "wax+"), f"upload code tried to write {file}"
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", no_writes)
    r = client.post("/api/onboarding/statement", data={"session_id": sid},
                    files={"file": ("extras.pdf", _sample_pdf_bytes(), "application/pdf")})
    monkeypatch.undo()
    assert r.status_code == 200
    body = r.json()
    assert body["profile_fields"]["income"]["salary"] == 6850
    assert body["profile_fields"]["source"]["statement_score"] == 58
    assert "income.salary" not in body["missing_fields"]
    session = sessions.get_session(sid)
    assert session.agent_profile["sources"]["income.salary"] == "extras"
    assert session.statement == {"score": 58, "risk_signals": ["Rată la IFN", "Pariuri online"]}


# ---------------------------------------------------------------- real-agent path, agent faked

@pytest.fixture
def real_mode(monkeypatch):
    monkeypatch.setattr(onboarding_api, "llm_enabled", lambda: True)


def _fake_turn(patch: dict, finish: bool, reply: str = "Notat!"):
    def turn(session_id, profile, convo, *args):
        prof.merge(profile, patch, "conversație")
        convo["done"] = finish
        yield {"type": "done", "text": reply, "tool_calls": []}
    return turn


def test_real_message_not_done_returns_missing_paths(real_mode, monkeypatch):
    monkeypatch.setattr(agent, "user_turn", _fake_turn({"name": "Ana", "age": 25}, finish=False, reply="Ce scop ai?"))
    sid = new_session()
    body = client.post("/api/onboarding/message", json={"session_id": sid, "text": "Sunt Ana, 25 de ani"}).json()
    assert body == {"reply": "Ce scop ai?", "missing_fields": body["missing_fields"], "done": False, "profile": None}
    assert "name" not in body["missing_fields"] and "goal.description" in body["missing_fields"]


def test_real_message_done_stores_profile_for_game_start(real_mode, monkeypatch):
    monkeypatch.setattr(agent, "user_turn", _fake_turn(AGENT_DATA, finish=True, reply="Gata!"))
    sid = new_session()
    body = client.post("/api/onboarding/message", json={"session_id": sid, "text": "..."}).json()
    assert body["done"] is True and body["missing_fields"] == []
    assert body["profile"]["recurring"]["rent"] == 1500
    assert sessions.get_session(sid).profile.name == "Andrei"
    state = client.post("/api/game/start", json={"session_id": sid}).json()["state"]
    assert state["monthly"]["expenses"]["health"] == 80  # game started from the onboarding profile


def test_real_message_done_but_invalid_profile_is_not_done(real_mode, monkeypatch):
    bad = {**AGENT_DATA, "age": "douăzeci"}
    monkeypatch.setattr(agent, "user_turn", _fake_turn(bad, finish=True))
    sid = new_session()
    body = client.post("/api/onboarding/message", json={"session_id": sid, "text": "..."}).json()
    assert body["done"] is False and "age" in body["missing_fields"]
    assert sessions.get_session(sid).profile is None


def test_real_message_api_error_is_502_and_keeps_state(real_mode, monkeypatch):
    def failing_turn(session_id, profile, convo, text):
        prof.merge(profile, {"name": "X"}, "conversație")
        raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
        yield  # pragma: no cover

    monkeypatch.setattr(agent, "user_turn", failing_turn)
    sid = new_session()
    assert client.post("/api/onboarding/message", json={"session_id": sid, "text": "..."}).status_code == 502
    assert sessions.get_session(sid).agent_profile == prof.empty()  # failed turn isn't committed


def test_real_statement_runs_pipeline_and_agent(real_mode, monkeypatch):
    calls = {}

    def fake_analyze(text):
        calls["text"] = text
        return SAMPLE_ANALYSIS

    def fake_statement_turn(session_id, profile, convo, filename, analysis, game_profile):
        prof.merge(profile, agent.statement_patch(analysis, game_profile), "extras")
        calls["filename"] = filename
        yield {"type": "done", "text": "Am citit extrasul.", "tool_calls": []}

    monkeypatch.setattr(onboarding_api, "analyze_statement", fake_analyze)
    monkeypatch.setattr(agent, "statement_turn", fake_statement_turn)
    sid = new_session()
    r = client.post("/api/onboarding/statement", data={"session_id": sid},
                    files={"file": ("extras.pdf", _sample_pdf_bytes(), "application/pdf")})
    assert r.status_code == 200
    body = r.json()
    assert "Ion Popescu" in calls["text"]  # real extract_text ran on the in-memory PDF
    assert calls["filename"] == "extras.pdf"
    assert body["reply"] == "Am citit extrasul."
    assert body["profile_fields"]["debts"][0]["monthly"] == 2310
    assert "cash" not in body["missing_fields"]


def test_real_statement_unreadable_is_422(real_mode):
    blank = pymupdf.open()
    blank.new_page()
    sid = new_session()
    r = client.post("/api/onboarding/statement", data={"session_id": sid},
                    files={"file": ("extras.pdf", blank.tobytes(), "application/pdf")})
    assert r.status_code == 422


def test_normalize_accepts_amount_strings():
    from app.analyzer import _normalize

    result = _normalize({
        "cheltuieli_lunare_estimate": "12",
        "cheltuieli_pe_categorii": [{"categorie": "uber", "suma": "670,92"}],
        "venituri": [{"tip": "salariu", "suma_totala": "1.858,33"}],
    })
    assert result["cheltuieli_lunare_estimate"] == pytest.approx(670.92)
    assert result["venit_lunar_estimat"] == pytest.approx(1858.33)


def test_llm_enabled_needs_key_and_no_mock(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("MOCK_LLM", "true")
    assert onboarding_api.llm_enabled() is False
    monkeypatch.setenv("MOCK_LLM", "false")
    assert onboarding_api.llm_enabled() is True
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    assert onboarding_api.llm_enabled() is False
