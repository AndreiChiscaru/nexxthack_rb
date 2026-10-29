"""Localization changes prose only, never the simulation's schema or values."""
import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.localization import LANGUAGE, resolve_language, agent_language_instruction

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "data/localization/en.json").read_text(encoding="utf-8"))

@pytest.mark.parametrize("header, expected", [(None,"ro"),("en-GB,en;q=0.9,ro;q=0.5","en"),("ro-RO","ro"),("fr,en;q=0.4","en"),("en;q=0,ro;q=0.8","ro"),("en;q=oops","ro"),("en;q=0.2,ro;q=0.9","ro")])
def test_language_negotiation(header, expected):
    assert resolve_language(header) == expected

def test_exported_catalog_matches_source():
    exported = json.loads((ROOT / "raiffquest/localization/game_en.json").read_text(encoding="utf-8"))
    assert exported == CATALOG

def test_all_event_and_product_copy_is_translated():
    for event in json.loads((ROOT / "data/events.json").read_text(encoding="utf-8")):
        for text in [event["title"], event["text"], *(o["label"] for o in event["options"])]:
            assert text in CATALOG, text
    for product in json.loads((ROOT / "data/products.json").read_text(encoding="utf-8")):
        for field in ("name", "terms", "conditions", "best_for", "cautions"):
            if product.get(field):
                assert product[field] in CATALOG, (product["id"], field)

def test_locale_is_request_scoped_and_catalog_remains_canonical(monkeypatch):
    from app.api import onboarding
    observed = []
    original = onboarding._mock_message
    def record(session):
        observed.append((LANGUAGE.get(), agent_language_instruction()))
        return original(session)
    monkeypatch.setattr(onboarding, "_mock_message", record)
    monkeypatch.setattr(onboarding, "llm_enabled", lambda: False)
    with TestClient(app) as client:
        sid = client.post("/api/session").json()["session_id"]
        for language in ("en", "ro"):
            response = client.post("/api/onboarding/message", headers={"Accept-Language":language}, json={"session_id":sid,"text":"Hello"})
            assert response.status_code == 200
        ro = client.get("/api/products").json()
        en = client.get("/api/products",headers={"Accept-Language":"en"}).json()
        assert ro == en  # UI renders translations; identifiers and source data never mutate.
    assert [x[0] for x in observed] == ["en", "ro"]
    assert "English" in observed[0][1] and "Review your profile" in observed[0][1]
    assert "Romanian" in observed[1][1]
    assert LANGUAGE.get() == "ro"

def test_concurrent_language_contexts_do_not_leak():
    async def scenario():
        async def request(language):
            token = LANGUAGE.set(language)
            try:
                await asyncio.sleep(0)
                return LANGUAGE.get()
            finally:
                LANGUAGE.reset(token)
        return await asyncio.gather(request("en"), request("ro"), request("en"))
    assert asyncio.run(scenario()) == ["en","ro","en"]

def test_language_reaches_llm_system(monkeypatch):
    from app.agents import llm
    systems = []
    monkeypatch.setattr(llm.anthropic, "Anthropic", lambda: object())
    def step(client, system, history, tools, max_tokens):
        systems.append(system)
        yield {"type":"_step","content":[{"type":"text","text":"Hello!"}],"stop_reason":"end_turn"}
    monkeypatch.setattr(llm,"_stream_step",step)
    token = LANGUAGE.set("en")
    try:
        result = llm.run_agent("Răspunde în română.", [{"role":"user","content":"Hello"}], [])
    finally:
        LANGUAGE.reset(token)
    assert result["text"] == "Hello!"
    assert systems[0].endswith(agent_language_instruction()) is False
    assert "overrides earlier instructions" in systems[0]
    assert "Do not translate tool names, JSON keys, IDs, enum values" in systems[0]
