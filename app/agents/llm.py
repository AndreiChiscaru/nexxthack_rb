"""Claude tool-use loop shared by all agents, streamed as events. Histories are plain JSON so they can be stored per session."""
import json
import os
from dataclasses import dataclass
from typing import Callable, Iterator

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


def _stream_step(client, system: str, history: list, tools: list[Tool], max_tokens: int) -> Iterator[dict]:
    """One model call. Yields text deltas and tool starts; the last event is {"type": "_step", content, stop_reason}."""
    kwargs = {"tools": [tool.spec() for tool in tools]} if tools else {}
    stream = client.messages.create(model=AGENT_MODEL, max_tokens=max_tokens, system=system,
                                    messages=history, stream=True, **kwargs)
    blocks: dict[int, dict] = {}
    stop_reason = None
    for event in stream:
        kind = event.type
        if kind == "content_block_start":
            block = event.content_block
            if block.type == "text":
                blocks[event.index] = {"type": "text", "text": ""}
            elif block.type == "tool_use":
                blocks[event.index] = {"type": "tool_use", "id": block.id, "name": block.name, "json": ""}
                yield {"type": "tool_start", "name": block.name}
        elif kind == "content_block_delta":
            block = blocks.get(event.index)
            delta = event.delta
            if block is None:
                continue
            if delta.type == "text_delta":
                piece = delta.text.replace("*", "")
                block["text"] += piece
                if piece:
                    yield {"type": "text", "delta": piece}
            elif delta.type == "input_json_delta":
                block["json"] += delta.partial_json
        elif kind == "message_delta":
            stop_reason = getattr(event.delta, "stop_reason", None) or stop_reason
    content = []
    for index in sorted(blocks):
        block = blocks[index]
        if block["type"] == "text":
            if block["text"]:
                content.append({"type": "text", "text": block["text"]})
        else:
            try:
                args = json.loads(block["json"]) if block["json"].strip() else {}
            except json.JSONDecodeError:
                args = {}
            content.append({"type": "tool_use", "id": block["id"], "name": block["name"], "input": args})
    yield {"type": "_step", "content": content, "stop_reason": stop_reason}


def stream_agent(system: str, history: list, tools: list[Tool], max_tokens: int = 1600) -> Iterator[dict]:
    """Runs one agent turn (with tool calls) on `history`, mutated in place. Yields
    {"type": "text", "delta"}, {"type": "tool_start", "name"}, {"type": "tool_end", "name", "summary"}
    and finally {"type": "done", "text", "tool_calls"}."""
    system += "\nScrie text simplu pentru utilizator, fără asteriscuri și fără markdown."
    client = anthropic.Anthropic()
    by_name = {tool.name: tool for tool in tools}
    calls: list[dict] = []
    texts: list[str] = []
    for _ in range(MAX_STEPS):
        step = None
        for event in _stream_step(client, system, history, tools, max_tokens):
            if event["type"] == "_step":
                step = event
            else:
                yield event
        content = step["content"]
        history.append({"role": "assistant", "content": content or [{"type": "text", "text": "..."}]})

        step_text = "".join(c["text"] for c in content if c["type"] == "text").strip()
        if step_text:
            texts.append(step_text)
            yield {"type": "text", "delta": "\n\n"}
        uses = [c for c in content if c["type"] == "tool_use"]
        if not uses and not texts:
            add_user_text(history, "(Scrie acum răspunsul final pentru utilizator, pe baza rezultatelor uneltelor.)")
            continue
        if not uses:
            yield {"type": "done", "text": "\n\n".join(texts), "tool_calls": calls}
            return

        results = []
        for use in uses:
            tool = by_name.get(use["name"])
            try:
                output = tool.handler(**use["input"]) if tool else {"error": f"Unealtă necunoscută: {use['name']}"}
            except Exception as exc:  # tool errors go back to the model, which can recover
                output = {"error": str(exc)}
            call = {"name": use["name"], "args": use["input"], "summary": _summary(output)}
            calls.append(call)
            yield {"type": "tool_end", **call}
            results.append({"type": "tool_result", "tool_use_id": use["id"],
                            "content": json.dumps(output, ensure_ascii=False, default=str)})
        history.append({"role": "user", "content": results})

    fallback = "Am folosit prea mulți pași pentru această întrebare. Poți reformula mai concret?"
    history.append({"role": "assistant", "content": [{"type": "text", "text": fallback}]})
    yield {"type": "text", "delta": fallback}
    yield {"type": "done", "text": "\n\n".join(texts + [fallback]), "tool_calls": calls}


def chat_turn(convo: dict, system: str, tools: list[Tool], max_tokens: int = 1600) -> Iterator[dict]:
    """Streams one turn and appends the final assistant message to the conversation's display list."""
    for event in stream_agent(system, convo["history"], tools, max_tokens):
        if event["type"] == "done":
            convo["display"].append({"role": "assistant", "text": event["text"], "tool_calls": event["tool_calls"]})
        yield event


def drain(events: Iterator[dict]) -> dict:
    result = {"text": "", "tool_calls": []}
    for event in events:
        if event["type"] == "done":
            result = {"text": event["text"], "tool_calls": event["tool_calls"]}
    return result


def run_agent(system: str, history: list, tools: list[Tool], max_tokens: int = 1600) -> dict:
    for event in stream_agent(system, history, tools, max_tokens):
        if event["type"] == "done":
            return {"text": event["text"], "tool_calls": event["tool_calls"]}
    return {"text": "", "tool_calls": []}
