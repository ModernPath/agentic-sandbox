import json

import pytest

from blocks_fakes import RecordingTransport
from sandbox_blocks.llm import AnthropicLLM, AzureOpenAILLM, GeminiLLM, OpenAILLM
from sandbox_blocks.tools import Tool


class ScriptedTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append({"url": url, "headers": headers, "body": body})
        return self.responses.pop(0)


def echo_tool(calls):
    def handler(arguments):
        calls.append(arguments)
        return {"echo": arguments["text"]}
    return Tool(name="echo", description="Echo text.",
                parameters={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
                handler=handler)


def openai_call(call_id="call_1", name="echo", arguments=None):
    return {"output": [{"type": "function_call", "call_id": call_id, "name": name,
                        "arguments": json.dumps(arguments or {"text": "hi"})}]}


def openai_text(text):
    return {"output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}]}


def test_openai_tool_loop_sends_function_tool_and_returns_output():  # T-1
    seen = []
    transport = ScriptedTransport(openai_call(), openai_text("Done: hi"))
    llm = OpenAILLM(api_key="k", model="gpt-6-luna", transport=transport)
    run = llm.run_with_tools("Say hi", tools=[echo_tool(seen)])
    first, second = transport.calls
    assert first["body"]["tools"] == [{"type": "function", "name": "echo", "description": "Echo text.",
                                       "parameters": echo_tool([]).parameters}]
    output_item = second["body"]["input"][-1]
    assert output_item == {"type": "function_call_output", "call_id": "call_1", "output": json.dumps({"echo": "hi"})}
    assert seen == [{"text": "hi"}]
    assert run.text == "Done: hi" and run.stop_reason == "completed"
    assert run.tool_calls[0].name == "echo" and run.tool_calls[0].result == {"echo": "hi"}


def test_azure_tool_loop_uses_api_key_header_and_deployment():  # T-2
    transport = ScriptedTransport(openai_call(), openai_text("ok"))
    llm = AzureOpenAILLM(endpoint="https://r.services.ai.azure.com", api_key="az", deployment="gpt-6-luna",
                         transport=transport)
    llm.run_with_tools("Say hi", tools=[echo_tool([])])
    assert transport.calls[0]["url"] == "https://r.services.ai.azure.com/openai/v1/responses"
    assert transport.calls[0]["headers"] == {"api-key": "az"}
    assert transport.calls[0]["body"]["model"] == "gpt-6-luna"


def test_gemini_tool_loop_returns_function_result_with_call_id():  # T-3
    transport = ScriptedTransport(
        {"id": "ia_1", "steps": [{"type": "function_call", "id": "call_g1", "name": "echo", "arguments": {"text": "hi"}}]},
        {"id": "ia_2", "steps": [{"type": "model_output", "content": [{"type": "text", "text": "Done"}]}]},
    )
    seen = []
    llm = GeminiLLM(api_key="g", model="gemini-3.8-flash", transport=transport)
    run = llm.run_with_tools("Say hi", tools=[echo_tool(seen)])
    second = transport.calls[1]["body"]
    assert second["previous_interaction_id"] == "ia_1"
    assert second["input"] == [{"type": "function_result", "name": "echo", "call_id": "call_g1",
                                "result": [{"type": "text", "text": json.dumps({"echo": "hi"})}]}]
    assert seen == [{"text": "hi"}] and run.text == "Done"


def test_anthropic_tool_loop_returns_tool_result_block():  # T-4 (offline; no live key)
    transport = ScriptedTransport(
        {"stop_reason": "tool_use", "content": [{"type": "tool_use", "id": "tu_1", "name": "echo", "input": {"text": "hi"}}]},
        {"stop_reason": "end_turn", "content": [{"type": "text", "text": "Done"}]},
    )
    llm = AnthropicLLM(api_key="a", model="claude-sonnet-5-5", transport=transport)
    run = llm.run_with_tools("Say hi", tools=[echo_tool([])])
    first_body = transport.calls[0]["body"]
    assert first_body["tools"] == [{"name": "echo", "description": "Echo text.",
                                    "input_schema": echo_tool([]).parameters}]
    result_message = transport.calls[1]["body"]["messages"][-1]
    assert result_message["role"] == "user"
    assert result_message["content"] == [{"type": "tool_result", "tool_use_id": "tu_1",
                                          "content": json.dumps({"echo": "hi"})}]
    assert run.text == "Done"


def test_call_limit_stops_the_loop_without_error():  # T-5
    transport = ScriptedTransport(*[openai_call(call_id=f"c{i}") for i in range(10)])
    llm = OpenAILLM(api_key="k", model="m", transport=transport)
    run = llm.run_with_tools("loop", tools=[echo_tool([])], max_calls=3)
    assert run.stop_reason == "max_calls" and run.text == ""
    assert len(run.tool_calls) == 3


def test_handler_error_is_sent_back_as_result_not_raised():  # T-6
    def failing(arguments):
        raise ValueError("note not found")
    tool = Tool(name="echo", description="x", parameters={"type": "object", "properties": {}}, handler=failing)
    transport = ScriptedTransport(openai_call(arguments={}), openai_text("Sorry"))
    run = OpenAILLM(api_key="k", model="m", transport=transport).run_with_tools("x", tools=[tool])
    sent = json.loads(transport.calls[1]["body"]["input"][-1]["output"])
    assert sent == {"error": "note not found"} and run.text == "Sorry"


def test_unknown_tool_name_returns_error_result():  # T-7
    transport = ScriptedTransport(openai_call(name="delete_everything"), openai_text("ok"))
    run = OpenAILLM(api_key="k", model="m", transport=transport).run_with_tools("x", tools=[echo_tool([])])
    sent = json.loads(transport.calls[1]["body"]["input"][-1]["output"])
    assert "unknown tool" in sent["error"].lower()
    assert run.tool_calls[0].result == sent


def test_history_is_rendered_as_transcript_in_the_prompt():  # T-8
    transport = ScriptedTransport(openai_text("Yes"))
    OpenAILLM(api_key="k", model="m", transport=transport).run_with_tools(
        "And now?", tools=[], history=[{"role": "user", "content": "Hello"},
                                       {"role": "assistant", "content": "Hi there"}])
    prompt = transport.calls[0]["body"]["input"][0]["content"]
    assert "User: Hello" in prompt and "Assistant: Hi there" in prompt and prompt.endswith("And now?")


def test_tool_loop_without_tools_is_plain_completion():  # T-9
    transport = ScriptedTransport(openai_text("Plain"))
    run = OpenAILLM(api_key="k", model="m", transport=transport).run_with_tools("x", tools=[])
    assert run.text == "Plain" and transport.calls[0]["body"].get("tools") in (None, [])
