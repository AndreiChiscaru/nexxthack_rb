"""Request-scoped language for agent prose; canonical financial data stays unchanged."""
from contextvars import ContextVar

LANGUAGE: ContextVar[str] = ContextVar("game_language", default="ro")


def resolve_language(header: str | None) -> str:
    """Honor ordered language preferences and regional tags; fall back to Romanian."""
    candidates = []
    for index, part in enumerate((header or "ro").split(",")):
        tag, *parameters = part.strip().lower().replace("_", "-").split(";")
        quality = 1.0
        for parameter in parameters:
            if parameter.strip().startswith("q="):
                try:
                    quality = float(parameter.strip()[2:])
                except ValueError:
                    quality = 0.0
        language = tag.split("-")[0]
        if language in ("ro", "en") and 0 < quality <= 1:
            candidates.append((quality, -index, language))
    return max(candidates)[2] if candidates else "ro"


def agent_language_instruction() -> str:
    if LANGUAGE.get() == "en":
        return (
            "\n\nPLAYER LANGUAGE: English. This overrides earlier instructions to reply in Romanian. "
            "Write all player-facing replies in natural, friendly, professional English. "
            "Keep user-provided names and goals intact. Explain Romanian terms briefly when helpful. "
            "Do not translate tool names, JSON keys, IDs, enum values or tax/legal form codes. "
            "Use the schema's original enum values in tool calls. In player-facing prose, translate "
            "mission titles and choice labels into English too, including quoted labels; do not quote Romanian labels. "
            "All monetary amounts remain in Romanian lei; do not convert currencies. "
            "Refer to UI buttons by their English names: Review your profile, Confirm and open the map, "
            "Add a statement, Add a document, Next month, Ask AIngel. "
            "After finishing onboarding, ask the player to choose Review your profile, then Confirm and open the map."
        )
    return "\n\nPLAYER LANGUAGE: Romanian. Răspunde natural în română, chiar dacă istoricul conține mesaje în engleză. Păstrează identificatorii și valorile enum din schema uneltelor."
