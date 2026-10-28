"""Shared user memory ("fișa utilizatorului"): facts any agent learns, visible to all the others."""
from datetime import datetime

from . import store
from .llm import Tool

TOPICS = ["scop", "afacere", "fiscal", "documente", "decizie", "preferinta", "risc", "familie", "cariera", "altele"]
AGENTS = {
    "onboarding": "Onboarding",
    "statement": "Analiză extras",
    "consultant": "Consultant",
    "angel": "AIngel",
    "investments": "Consultant de investiții",
    "business": "Contabil",
    "joc": "Joc",
}
MAX_NOTES = 60
PROMPT_NOTES = 25


def _month(session_id: str):
    game = store.load(session_id, "game")
    if isinstance(game, dict) and game.get("month") is not None:
        return game["month"]
    # The journey keeps its month on the live session, not in the demo store.
    from ..sessions import find_session
    live = find_session(session_id)
    if live is not None and live.sim is not None:
        return live.month
    return None


def load(session_id: str) -> list[dict]:
    return store.load(session_id, "memory", [])


def add(session_id: str, agent: str, topic: str, text: str) -> dict:
    notes = load(session_id)
    text = " ".join(str(text).split())[:400]
    for note in notes:
        if note["topic"] == topic and note["text"].lower() == text.lower():
            return note
    note = {"agent": agent, "topic": topic if topic in TOPICS else "altele", "text": text,
            "month": _month(session_id), "at": datetime.now().strftime("%H:%M")}
    notes.append(note)
    store.save(session_id, "memory", notes[-MAX_NOTES:])
    return note


def prompt_block(session_id: str) -> str:
    notes = load(session_id)[-PROMPT_NOTES:]
    if not notes:
        return "Fișa utilizatorului (memorie comună a agenților): încă goală."
    lines = [f"- [{AGENTS.get(n['agent'], n['agent'])}, {n['topic']}{', luna ' + str(n['month']) if n['month'] is not None else ''}] {n['text']}"
             for n in notes]
    return ("Fișa utilizatorului (memorie comună: ce au aflat ceilalți agenți; folosește-o, nu întreba din nou):\n" + "\n".join(lines))


RULE = ("Când afli ceva important și durabil despre utilizator, care nu e deja în profil sau în fișă (o intenție, o decizie, "
        "o preferință, o problemă, un document), salvează-l cu remember, într-o propoziție scurtă. Nu salva detalii banale.")


def tool(session_id: str, agent: str) -> Tool:
    def remember(topic: str, note: str):
        add(session_id, agent, topic, note)
        return {"ok": True, "summary": f"notat în fișă ({topic}): {note[:80]}"}

    return Tool("remember", "Salvează în fișa comună a utilizatorului un fapt util și pentru ceilalți agenți.",
                {"type": "object", "properties": {"topic": {"type": "string", "enum": TOPICS},
                                                  "note": {"type": "string", "description": "o propoziție, la persoana a treia"}},
                 "required": ["topic", "note"]}, remember)
