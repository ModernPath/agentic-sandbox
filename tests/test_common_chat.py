"""Common chat tests (specs/features/common-chat). Offline: scripted models, fake agents, real CLI subprocess."""

import json
import os
import sys
from pathlib import Path

from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from sandbox_blocks.llm import LLMResponse
from sandbox_blocks.tools import ToolCall, ToolRun, tool_from_function
from sandbox_host.app import create_app
from sandbox_host.cli_bridge import CommandError, cli_env, run_command
from sandbox_host.config import HostSettings
from sandbox_host.migrations import apply_agent_migrations
from sandbox_host.registry import AgentSpec, CliSpec
from sandbox_host.testing import memory_engine, signed_in_client

ROOT = Path(__file__).resolve().parents[1]
CSV = b"name,value\nalpha,1\nbeta,2\n"


def greet(who: str) -> dict:
    """Say hello to someone."""
    return {"greeting": f"hello {who}"}


def shout(text: str) -> dict:
    """Shout a phrase."""
    return {"shout": text.upper()}


def make_spec(name, functions=(), cli=None, broken=False):
    def chat_tools(ctx):
        if broken:
            raise RuntimeError("tools cannot be built")
        return [tool_from_function(fn) for fn in functions]

    return AgentSpec(name=name, title=name.title(), description=f"{name} agent", router=APIRouter(),
                     chat_tools=chat_tools if (functions or broken) else None, cli=cli)


class ScriptedLLM:
    provider = "fake"
    model = "fake-1"

    def __init__(self, script=(), reply="Done."):
        self.script = script
        self.reply = reply
        self.prompt = None
        self.history = None
        self.tool_names = None
        self.results = {}

    def complete(self, prompt, system=None):
        raise AssertionError("the chat must use run_with_tools")

    def complete_with_image(self, prompt, image, mime, system=None):
        raise AssertionError("not used")

    def run_with_tools(self, prompt, *, system=None, history=(), tools=(), max_calls=8):
        self.prompt = prompt
        self.history = list(history)
        self.tool_names = [t.name for t in tools]
        by_name = {t.name: t for t in tools}
        calls = []
        for name, args in self.script:
            result = by_name[name].handler(args)
            self.results[name] = result
            calls.append(ToolCall(name=name, arguments=args, result=result))
        return ToolRun(text=self.reply, provider="fake", model="fake-1", tool_calls=tuple(calls))


def client(agents, llm=None, engine=None):
    llm = llm or ScriptedLLM()
    app = create_app(HostSettings.from_env({}), agents=agents, engine=engine or memory_engine(),
                     services={"chat": {"llm": llm}})
    return signed_in_client(app), llm


def chat(c, message="hi", history=(), attachment_ids=()):
    return c.post("/api/chat", json={"message": message, "history": list(history),
                                     "attachment_ids": list(attachment_ids)})


# C-1 to C-5: chat tools and turns
def test_c1_chat_offers_every_agents_tools_with_prefixes():  # C-1
    c, llm = client([make_spec("alpha", [greet]), make_spec("beta", [shout]), make_spec("quiet")])
    assert chat(c).status_code == 200
    names = set(llm.tool_names)
    assert {"alpha__greet", "beta__shout", "run_agent_cli"} <= names
    assert not any(name.startswith("quiet__") for name in names)


def test_c2_reply_tool_names_and_history_are_passed_through():  # C-2
    llm = ScriptedLLM(script=(("alpha__greet", {"who": "Ada"}),), reply="Said hello.")
    c, _ = client([make_spec("alpha", [greet])], llm=llm)
    history = [{"role": "user", "content": "earlier"}]
    response = chat(c, "greet Ada", history)
    assert response.json() == {"reply": "Said hello.", "tool_calls": ["alpha__greet"]}
    assert llm.history == history
    assert llm.results["alpha__greet"] == {"greeting": "hello Ada"}


def test_c3_chat_limits_are_validated():  # C-3
    c, _ = client([])
    assert chat(c, history=[{"role": "user", "content": "x"}] * 21).status_code == 422
    assert chat(c, message="x" * 1001).status_code == 422
    assert chat(c, attachment_ids=["a" * 36] * 6).status_code == 422


def test_c4_no_model_is_503_with_a_fixed_message(monkeypatch):  # C-4
    for name in ("SANDBOX_LLM_PROVIDER", "GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    app = create_app(HostSettings.from_env({}), agents=[make_spec("alpha", [greet])], engine=memory_engine())
    response = chat(signed_in_client(app))
    assert response.status_code == 503 and "model" in response.json()["error"].lower()


def test_c5_an_agent_whose_tools_fail_is_skipped():  # C-5
    c, llm = client([make_spec("broken", broken=True), make_spec("alpha", [greet])])
    assert chat(c).status_code == 200
    assert "alpha__greet" in llm.tool_names
    assert not any(name.startswith("broken__") for name in llm.tool_names)


# C-6 to C-11: command-line bridge
def test_c6_cli_environment_keeps_only_allowed_keys():  # C-6
    env = cli_env({"PATH": "/bin", "DATABASE_URL": "db", "GEMINI_API_KEY": "k",
                   "SANDBOX_LLM_PROVIDER": "gemini", "RANDOM_TOKEN": "secret"})
    assert set(env) == {"PATH", "DATABASE_URL", "GEMINI_API_KEY", "SANDBOX_LLM_PROVIDER"}


def test_c7_undeclared_command_is_refused_without_running_anything():  # C-7
    spec = make_spec("alpha", cli=CliSpec(module="competitor_watch.cli", commands=("list",)))
    try:
        run_command(spec, "delete", [], {})
    except CommandError as error:
        assert "not allowed" in str(error)
    else:
        raise AssertionError("expected CommandError")


def test_c8_argument_limits_are_enforced():  # C-8
    spec = make_spec("alpha", cli=CliSpec(module="competitor_watch.cli", commands=("list",)))
    for args in (["x"] * 13, ["y" * 201]):
        try:
            run_command(spec, "list", args, {})
        except CommandError:
            continue
        raise AssertionError("expected CommandError")


def _temp_database(tmp_path):
    db = tmp_path / "cli.db"
    engine = create_engine(f"sqlite:///{db}")
    apply_agent_migrations(engine, "competitor-watch", ROOT / "agents/competitor_watch/migrations")
    return db


def _cli_env(db):
    return {"PATH": os.environ.get("PATH", ""), "DATABASE_URL": f"sqlite:///{db}",
            "PYTHONPATH": f"{ROOT / 'src'}:{ROOT / 'agents'}"}


def test_c9_real_cli_command_returns_its_json(tmp_path):  # C-9
    spec = make_spec("competitor-watch", cli=CliSpec(module="competitor_watch.cli", commands=("list",)))
    result = run_command(spec, "list", [], _cli_env(_temp_database(tmp_path)))
    assert result == {"ok": True, "result": []}


def test_c10_arguments_are_literal_not_shell(tmp_path):  # C-10
    spec = make_spec("competitor-watch", cli=CliSpec(module="competitor_watch.cli", commands=("list",)))
    result = run_command(spec, "list", ["; echo injected"], _cli_env(_temp_database(tmp_path)))
    assert result["ok"] is False and "injected" not in json.dumps(result)


def test_c11_chat_runs_an_agent_cli_command(tmp_path):  # C-11
    spec = make_spec("competitor-watch", cli=CliSpec(module="competitor_watch.cli", commands=("list",)))
    db = _temp_database(tmp_path)
    llm = ScriptedLLM(script=(("run_agent_cli", {"agent": "competitor-watch", "command": "list", "args": ""}),))
    engine = create_engine(f"sqlite:///{db}")
    c, _ = client([spec], llm=llm, engine=engine)
    response = chat(c, "list competitors")
    assert response.json()["tool_calls"] == ["run_agent_cli"]
    assert llm.results["run_agent_cli"] == {"ok": True, "result": []}


# C-12 to C-16: attachments, through the real file reader
def file_reader_spec():
    from file_reader.api import make_agent_spec
    return make_agent_spec()


def test_c12_attachment_is_stored_by_the_file_reader():  # C-12
    c, _ = client([file_reader_spec()])
    response = c.post("/api/chat/attachments", files={"file": ("people.csv", CSV, "text/csv")})
    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "people.csv" and body["kind"] == "csv" and body["id"]
    assert "content" not in body


def test_c13_attachment_with_no_handler_is_404():  # C-13
    c, _ = client([make_spec("alpha", [greet])])
    assert c.post("/api/chat/attachments", files={"file": ("a.csv", CSV, "text/csv")}).status_code == 404


def test_c14_attachment_over_10_mb_is_413():  # C-14
    c, _ = client([file_reader_spec()])
    big = b"a" * (10 * 1024 * 1024 + 1)
    assert c.post("/api/chat/attachments", files={"file": ("big.txt", big, "text/plain")}).status_code == 413


def test_c15_attached_file_is_named_to_the_model_and_readable_through_tools():  # C-15
    llm = None
    c, llm = client([file_reader_spec()])
    file_id = c.post("/api/chat/attachments", files={"file": ("people.csv", CSV, "text/csv")}).json()["id"]
    llm.script = (("file_reader__read_file", {"file_id": file_id}),)
    response = chat(c, "What is in the file?", attachment_ids=[file_id])
    assert file_id in llm.prompt
    assert response.json()["tool_calls"] == ["file_reader__read_file"]
    assert llm.results["file_reader__read_file"]["kind"] == "csv"


def test_c16_unsupported_attachment_type_is_415():  # C-16
    c, _ = client([file_reader_spec()])
    response = c.post("/api/chat/attachments", files={"file": ("tool.exe", b"MZ", "application/octet-stream")})
    assert response.status_code == 415 and "error" in response.json()


# C-17: front page
def test_c17_front_page_is_the_chat_without_a_redirect():  # C-17
    c, _ = client([])
    response = c.get("/", follow_redirects=False)
    assert response.status_code == 200 and 'id="chat-log"' in response.text


def test_c18_research_without_search_returns_a_fixed_message():  # C-18
    from research_brief.store import BriefStore
    from research_brief.tools import build_tools as research_tools

    tools = {t.name: t for t in research_tools(BriefStore(memory_engine()), None, None, None)}
    result = tools["research_topic"].handler({"topic": "solid state batteries"})
    assert result == {"error": "Search and model must be configured to research a topic."}


def test_c19_chat_can_be_limited_to_one_agent():  # C-19
    llm = ScriptedLLM(reply="ok")
    c, llm = client([make_spec("alpha", [greet]), make_spec("beta", [shout])], llm=llm)
    response = c.post("/api/chat", json={"message": "hi", "history": [], "agent": "alpha"})
    assert response.status_code == 200
    assert "alpha__greet" in llm.tool_names
    assert not any(name.startswith("beta__") for name in llm.tool_names)


def test_c20_unknown_agent_scope_is_422():  # C-20
    c, _ = client([make_spec("alpha", [greet])])
    response = c.post("/api/chat", json={"message": "hi", "history": [], "agent": "nope"})
    assert response.status_code == 422
