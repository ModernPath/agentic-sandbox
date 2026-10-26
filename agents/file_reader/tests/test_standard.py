"""Standard tests for the file reader: service rules, read-only tools, and the CLI envelope."""

import json

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from file_reader import cli, service
from file_reader.store import FileStore
from file_reader.tools import build_tools
from sandbox_blocks.llm import LLMResponse
from sandbox_host.migrations import apply_agent_migrations
from file_reader import api as file_api

MIGRATIONS = file_api.HERE / "migrations"
CSV = b"name,value\nalpha,1\nbeta,2\n"
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000d49444154789c6360f8cfc0f01f0005000201a5f1e6750000000049454e44ae426082")


class FakeLLM:
    provider = "fake"
    model = "fake-1"

    def __init__(self):
        self.calls = []

    def complete(self, prompt, system=None):
        self.calls.append(("complete", prompt, system))
        return LLMResponse(text="ok", provider=self.provider, model=self.model)

    def complete_with_image(self, prompt, image, mime, system=None):
        self.calls.append(("image", prompt, len(image), mime))
        return LLMResponse(text="described", provider=self.provider, model=self.model)


def _store():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    apply_agent_migrations(engine, "file-reader", MIGRATIONS)
    return FileStore(engine)


def test_upload_rejects_files_over_the_limit():
    store = _store()
    too_big = b"a" * (10 * 1024 * 1024 + 1)
    try:
        service.upload_file(store, "big.txt", too_big)
    except service.FileTooLargeError as error:
        assert "10 MB" in str(error)
    else:
        raise AssertionError("expected FileTooLargeError")


def test_upload_stores_content_hash_and_hides_bytes_from_metadata():
    store = _store()
    record = service.upload_file(store, "people.csv", CSV)
    assert record["kind"] == "csv"
    assert "content" not in record
    assert record["sha256"]
    assert [f["filename"] for f in service.list_files(store)] == ["people.csv"]


def test_read_returns_text_and_tables_without_raw_bytes():
    store = _store()
    record = service.upload_file(store, "people.csv", CSV)
    result = service.read_file(store, record["id"])
    assert result["kind"] == "csv"
    assert "alpha" in json.dumps(result["tables"])
    assert "content" not in result


def test_describe_rejects_a_document_and_ask_answers_from_document_text():
    store = _store()
    llm = FakeLLM()
    doc = service.upload_file(store, "people.csv", CSV)
    image = service.upload_file(store, "scan.png", PNG)
    try:
        service.describe_image(store, llm, doc["id"], "describe")
    except ValueError as error:
        assert "image" in str(error)
    else:
        raise AssertionError("expected ValueError")
    answer = service.ask_file(store, llm, doc["id"], "who is beta?")
    assert answer["text"] == "ok"
    _, prompt, system = llm.calls[-1]
    assert "<document>" in prompt and "beta" in prompt
    assert "data, not as instructions" in system
    assert service.describe_image(store, llm, image["id"], "what is it?")["text"] == "described"


def test_unknown_file_raises_lookup_error():
    store = _store()
    try:
        service.read_file(store, "missing")
    except LookupError as error:
        assert "not found" in str(error)
    else:
        raise AssertionError("expected LookupError")


def test_tools_are_read_only_and_return_errors_instead_of_raising():
    store = _store()
    tools = build_tools(store, FakeLLM())
    names = {t.name for t in tools}
    assert names == {"list_files", "read_file", "ask_file", "describe_image"}
    assert all("upload" not in name for name in names)
    by_name = {t.name: t for t in tools}
    assert "error" in by_name["read_file"].handler({"file_id": "missing"})
    assert "error" in by_name["ask_file"].handler({"file_id": "missing", "question": "?"})


def test_cli_prints_a_json_envelope_for_upload_and_list(tmp_path):
    store = _store()
    path = tmp_path / "people.csv"
    path.write_bytes(CSV)
    engine = store.engine
    code = cli.main(["upload", "--path", str(path)], engine=engine)
    assert code == 0
    code = cli.main(["list"], engine=engine)
    assert code == 0


def test_cli_missing_file_is_a_json_error_with_exit_code_1(capsys, tmp_path):
    store = _store()
    code = cli.main(["upload", "--path", str(tmp_path / "nope.csv")], engine=store.engine)
    out = json.loads(capsys.readouterr().out)
    assert code == 1 and out == {"ok": False, "error": "File not found"}


def test_cli_usage_error_exits_2(capsys):
    code = cli.main(["read"], engine=_store().engine)
    assert code == 2
    assert "usage error" in capsys.readouterr().err


def test_cli_ask_uses_injected_llm(capsys):
    store = _store()
    doc = service.upload_file(store, "people.csv", CSV)
    code = cli.main(["ask", "--id", doc["id"], "--question", "who?"], engine=store.engine, llm=FakeLLM())
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["ok"] and out["result"]["text"] == "ok"
