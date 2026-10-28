"""Claude tool-use loop shared by all agents. Histories are plain JSON so they can be stored per session."""
import json
import os
from dataclasses import dataclass
from typing import Callable

import anthropic

AGENT_MODEL = os.getenv("AGENT_MODEL", "claude-haiku-5-5")
MAX_STEPS = 8


@dataclass
class Tool:
    name: str
    description: str
    schema: dict
    handler: Callable[..., dict]

    def spec(self) -> dict:
        return {"name": self.name, "description": self.description, "input_schema": self.schema}


def add_user_text(history: list, text: str) -> None:
    """Appends user text, merging into the previous user turn so roles keep alternating."""
    block = {"type": "text", "text": text}
    if history and history[-1]["role"] == "user":
        history[-1]["content"].append(block)
    else:
        history.append({"role": "user", "content": [block]})


def _summary(result: dict) -> str:
    if isinstance(result, dict) and result.get("summary"):
        return str(result["summary"])
    raw = json.dumps(result, ensure_ascii=False, default=str)
    return raw if len(raw) <= 220 else raw[:217] + "..."


def run_agent(system: str, history: list, tools: list[Tool], max_tokens: int = 1600) -> dict:
    """Runs one agent turn (with tool calls) on `history`, which is mutated in place."""
    client = anthropic.Anthropic()
    by_name = {tool.name: tool for tool in tools}
    calls: list[dict] = []
    for _ in range(MAX_STEPS):
        kwargs = {"tools": [tool.spec() for tool in tools]} if tools else {}
        response = client.messages.create(model=AGENT_MODEL, max_tokens=max_tokens, system=system,
                                          messages=history, **kwargs)
        content = []
        for block in response.content:
            if block.type == "text":
                content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                content.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
        history.append({"role": "assistant", "content": content or [{"type": "text", "text": "..."}]})

        uses = [c for c in content if c["type"] == "tool_use"]
        if not uses:
            text = "\n".join(c["text"] for c in content if c["type"] == "text").strip()
            return {"text": text, "tool_calls": calls}

        results = []
        for use in uses:
            tool = by_name.get(use["name"])
            try:
                output = tool.handler(**use["input"]) if tool else {"error": f"Unealtă necunoscută: {use['name']}"}
            except Exception as exc:  # tool errors go back to the model, which can recover
                output = {"error": str(exc)}
            calls.append({"name": use["name"], "args": use["input"], "summary": _summary(output)})
            results.append({"type": "tool_result", "tool_use_id": use["id"],
                            "content": json.dumps(output, ensure_ascii=False, default=str)})
        history.append({"role": "user", "content": results})

    fallback = "Am folosit prea mulți pași pentru această întrebare. Poți reformula mai concret?"
    history.append({"role": "assistant", "content": [{"type": "text", "text": fallback}]})
    return {"text": fallback, "tool_calls": calls}
