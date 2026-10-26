"""Provider-neutral tool calling: the model asks for tools, our code runs them, results go back.

Each provider keeps its own wire format; agents only see Tool and ToolRun.
Handler errors and unknown tool names are returned to the model as {"error": ...}.
The loop stops after max_calls tool calls with stop_reason "max_calls".
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence

import inspect
import re
import typing

from .errors import ProviderError


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: Mapping[str, Any]
    handler: Callable[[dict], Any]


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict
    result: Any


@dataclass(frozen=True)
class ToolRun:
    text: str
    provider: str
    model: str
    tool_calls: tuple = field(default_factory=tuple)
    stop_reason: str = "completed"


def render_prompt(prompt: str, history: Sequence[Mapping[str, str]] = ()) -> str:
    """Conversation so far, as plain transcript text, followed by the new user message."""
    if not history:
        return prompt
    lines = ["Conversation so far:"]
    for turn in history:
        speaker = "User" if turn.get("role") == "user" else "Assistant"
        lines.append(f"{speaker}: {turn.get('content', '')}")
    lines.append("")
    lines.append(prompt)
    return "\n".join(lines)


def _execute(tools: Mapping[str, Tool], name: str, arguments: dict) -> Any:
    tool = tools.get(name)
    if tool is None:
        return {"error": f"unknown tool: {name}"}
    try:
        return tool.handler(arguments)
    except Exception as error:  # the model sees a short message, never a traceback
        return {"error": str(error) or "tool failed"}


def _tool_map(tools: Sequence[Tool]) -> dict:
    return {tool.name: tool for tool in tools}


def _openai_text(payload: dict) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"].strip()
    return "".join(
        item.get("text", "")
        for output in payload.get("output", []) or []
        for item in output.get("content", []) or []
        if item.get("type") == "output_text"
    ).strip()


def run_openai_style(*, transport, url: str, headers: Mapping[str, str], model: str, provider: str,
                     prompt: str, system: Optional[str], history, tools: Sequence[Tool], max_calls: int,
                     timeout: float) -> ToolRun:
    tool_map = _tool_map(tools)
    specs = [{"type": "function", "name": t.name, "description": t.description, "parameters": dict(t.parameters)}
             for t in tools]
    items: list = [{"role": "user", "content": render_prompt(prompt, history)}]
    records: list[ToolCall] = []
    while True:
        body: dict[str, Any] = {"model": model, "input": items}
        if system:
            body["instructions"] = system
        if specs:
            body["tools"] = specs
        payload = transport(url, headers, body, timeout)
        output = payload.get("output") or []
        calls = [item for item in output if item.get("type") == "function_call"]
        if not calls:
            return ToolRun(text=_openai_text(payload), provider=provider, model=model, tool_calls=tuple(records))
        if len(records) + len(calls) > max_calls:
            return ToolRun(text="", provider=provider, model=model, tool_calls=tuple(records), stop_reason="max_calls")
        items.extend(output)
        for call in calls:
            arguments = json.loads(call.get("arguments") or "{}")
            result = _execute(tool_map, call["name"], arguments)
            records.append(ToolCall(name=call["name"], arguments=arguments, result=result))
            items.append({"type": "function_call_output", "call_id": call["call_id"], "output": json.dumps(result)})


def run_gemini(*, transport, url: str, headers: Mapping[str, str], model: str, prompt: str,
               system: Optional[str], history, tools: Sequence[Tool], max_calls: int, timeout: float) -> ToolRun:
    tool_map = _tool_map(tools)
    specs = [{"type": "function", "name": t.name, "description": t.description, "parameters": dict(t.parameters)}
             for t in tools]
    text_input = render_prompt(prompt, history)
    if system:
        text_input = f"{system}\n\n{text_input}"
    body: dict[str, Any] = {"model": model, "input": text_input}
    if specs:
        body["tools"] = specs
    records: list[ToolCall] = []
    while True:
        payload = transport(url, headers, body, timeout)
        steps = payload.get("steps", []) or []
        calls = [step for step in steps if step.get("type") == "function_call"]
        if not calls:
            text = "".join(
                item.get("text", "")
                for step in steps if step.get("type") == "model_output"
                for item in step.get("content", []) or []
                if item.get("type") == "text"
            ).strip()
            return ToolRun(text=text, provider="gemini", model=model, tool_calls=tuple(records))
        if len(records) + len(calls) > max_calls:
            return ToolRun(text="", provider="gemini", model=model, tool_calls=tuple(records), stop_reason="max_calls")
        results = []
        for call in calls:
            arguments = call.get("arguments") or {}
            result = _execute(tool_map, call["name"], arguments)
            records.append(ToolCall(name=call["name"], arguments=arguments, result=result))
            results.append({"type": "function_result", "name": call["name"], "call_id": call["id"],
                            "result": [{"type": "text", "text": json.dumps(result)}]})
        body = {"model": model, "previous_interaction_id": payload["id"], "input": results}
        if specs:
            body["tools"] = specs


def run_anthropic(*, transport, url: str, headers: Mapping[str, str], model: str, prompt: str,
                  system: Optional[str], history, tools: Sequence[Tool], max_calls: int, max_tokens: int,
                  timeout: float) -> ToolRun:
    tool_map = _tool_map(tools)
    specs = [{"name": t.name, "description": t.description, "input_schema": dict(t.parameters)} for t in tools]
    messages: list = [{"role": "user", "content": render_prompt(prompt, history)}]
    records: list[ToolCall] = []
    while True:
        body: dict[str, Any] = {"model": model, "max_tokens": max_tokens, "messages": messages}
        if system:
            body["system"] = system
        if specs:
            body["tools"] = specs
        payload = transport(url, headers, body, timeout)
        content = payload.get("content") or []
        uses = [block for block in content if block.get("type") == "tool_use"]
        if not uses:
            text = "".join(block.get("text", "") for block in content if block.get("type") == "text").strip()
            return ToolRun(text=text, provider="anthropic", model=model, tool_calls=tuple(records))
        if len(records) + len(uses) > max_calls:
            return ToolRun(text="", provider="anthropic", model=model, tool_calls=tuple(records), stop_reason="max_calls")
        messages.append({"role": "assistant", "content": content})
        results = []
        for use in uses:
            arguments = use.get("input") or {}
            result = _execute(tool_map, use["name"], arguments)
            records.append(ToolCall(name=use["name"], arguments=arguments, result=result))
            results.append({"type": "tool_result", "tool_use_id": use["id"], "content": json.dumps(result)})
        messages.append({"role": "user", "content": results})


_JSON_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean"}


def tool_from_function(fn: Callable[..., Any], *, name: Optional[str] = None, description: Optional[str] = None,
                       on_call: Optional[Callable[[str], None]] = None) -> Tool:
    """Describe a Python function as a Tool: schema from type hints and defaults, text from the docstring.

    Parameters must be annotated with str, int, float, or bool. The docstring's first paragraph is the
    description; an "Args:" section supplies per-parameter descriptions.
    """
    doc = inspect.getdoc(fn) or ""
    summary, arg_docs = _split_docstring(doc)
    hints = typing.get_type_hints(fn)
    properties: dict = {}
    required: list = []
    for param in inspect.signature(fn).parameters.values():
        hint = hints.get(param.name)
        if hint not in _JSON_TYPES:
            raise TypeError(f"{fn.__name__}.{param.name} must be annotated str, int, float, or bool")
        schema: dict = {"type": _JSON_TYPES[hint]}
        if param.name in arg_docs:
            schema["description"] = arg_docs[param.name]
        properties[param.name] = schema
        if param.default is inspect.Parameter.empty:
            required.append(param.name)
    parameters = {"type": "object", "properties": properties, "required": required}
    tool_name = name or fn.__name__

    def handler(arguments: dict) -> Any:
        if on_call is not None:
            on_call(tool_name)
        return fn(**arguments)

    return Tool(name=tool_name, description=description if description is not None else summary,
                parameters=parameters, handler=handler)


def _split_docstring(doc: str) -> tuple[str, dict]:
    head, _, rest = doc.partition("\nArgs:")
    summary = head.strip().split("\n\n")[0].replace("\n", " ").strip()
    arg_docs: dict = {}
    for line in rest.splitlines():
        match = re.match(r"^\s+(\w+):\s*(.+)$", line)
        if match:
            arg_docs[match.group(1)] = match.group(2).strip()
    return summary, arg_docs
