import base64

from host_test_client import SignedInTestClient as TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from file_reader.api import make_agent_spec
from sandbox_blocks.errors import ProviderError
from sandbox_blocks.llm import LLMResponse
from sandbox_host.app import create_app
from sandbox_host.config import HostSettings
from test_blocks_vision import IMAGE

BASE = "/api/agents/file-reader"


class FakeLLM:
    provider = "fake"
    model = "fake-model"

    def __init__(self):
        self.calls = []

    def complete(self, prompt, system=None):
        self.calls.append(("text", prompt, system))
        return LLMResponse(text="Answer from document", provider="fake", model="fake-model")

    def complete_with_image(self, prompt, image, mime, system=None):
        self.calls.append(("image", prompt, image, mime))
        return LLMResponse(text="A bar chart", provider="fake", model="fake-model")


class BrokenLLM(FakeLLM):
    def complete_with_image(self, prompt, image, mime, system=None):
        raise ProviderError("Provider returned HTTP 500")


def client(llm=None, engine=None):
    engine = engine if engine is not None else create_engine(
        "sqlite+pysqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    services = {"file_reader": {"llm": llm or FakeLLM()}}
    app = create_app(HostSettings.from_env({}), agents=[make_agent_spec()], engine=engine, services=services)
    return TestClient(app)


def upload(c, name, data, mime="application/octet-stream"):
    return c.post(f"{BASE}/files", files={"file": (name, data, mime)})


def test_upload_stores_metadata_and_lists_it():  # A-1
    with client() as c:
        data = b"objective,value\nPipeline,10\n"
        response = upload(c, "targets.csv", data, "text/csv")
        assert response.status_code == 201
        body = response.json()
        assert body["filename"] == "targets.csv" and body["size"] == len(data) and len(body["sha256"]) == 64
        assert [f["id"] for f in c.get(f"{BASE}/files").json()["files"]] == [body["id"]]


def test_file_over_10_mb_is_rejected_with_413():  # A-2
    with client() as c:
        response = upload(c, "big.txt", b"a" * (10 * 1024 * 1024 + 1))
        assert response.status_code == 413
        assert c.get(f"{BASE}/files").json()["files"] == []


def test_unsupported_type_is_rejected_with_415():  # A-3
    with client() as c:
        assert upload(c, "tool.exe", b"MZ").status_code == 415


def test_get_returns_parsed_rows_without_raw_bytes():  # A-4
    with client() as c:
        file_id = upload(c, "targets.csv", b"objective,value\nPipeline,10\n").json()["id"]
        body = c.get(f"{BASE}/files/{file_id}").json()
        assert body["kind"] == "csv"
        assert body["tables"]["csv"][:2] == [["objective", "value"], ["Pipeline", "10"]]
        assert "content" not in body


def test_describe_image_sends_bytes_to_vision_model():  # A-5
    llm = FakeLLM()
    with client(llm) as c:
        file_id = upload(c, "chart.png", IMAGE, "image/png").json()["id"]
        body = c.post(f"{BASE}/files/{file_id}/describe", json={"prompt": "What does the chart show?"}).json()
        assert body["text"] == "A bar chart" and body["model"] == "fake-model"
    assert llm.calls[0][0] == "image" and llm.calls[0][2] == IMAGE and llm.calls[0][3] == "image/png"


def test_describe_rejects_a_document():  # A-6
    with client() as c:
        file_id = upload(c, "notes.txt", b"plain text").json()["id"]
        response = c.post(f"{BASE}/files/{file_id}/describe", json={"prompt": "x"})
        assert response.status_code == 422 and "image" in response.json()["error"].lower()


def test_ask_sends_document_text_and_question_to_model():  # A-7
    llm = FakeLLM()
    with client(llm) as c:
        file_id = upload(c, "notes.txt", b"Revenue grew 20 percent.").json()["id"]
        body = c.post(f"{BASE}/files/{file_id}/ask", json={"question": "How much did revenue grow?"}).json()
        assert body["text"] == "Answer from document"
    kind, prompt, system = llm.calls[0]
    assert "Revenue grew 20 percent." in prompt and "How much did revenue grow?" in prompt
    assert "only" in system.lower()


def test_unknown_file_is_404():  # A-8
    with client() as c:
        assert c.get(f"{BASE}/files/nope").status_code == 404


def test_storage_unavailable_without_engine_is_503():  # A-9
    app = create_app(HostSettings.from_env({}), agents=[make_agent_spec()])
    with TestClient(app) as c:
        response = c.get(f"{BASE}/files")
        assert response.status_code == 503 and response.json()["error"]


def test_provider_failure_is_502_with_safe_message():  # A-10
    with client(BrokenLLM()) as c:
        file_id = upload(c, "chart.png", IMAGE, "image/png").json()["id"]
        response = c.post(f"{BASE}/files/{file_id}/describe", json={"prompt": "x"})
        assert response.status_code == 502 and "Traceback" not in response.text


def test_migration_creates_files_table_at_startup():  # A-11
    from sqlalchemy import text
    engine = create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    with client(engine=engine):
        with engine.connect() as conn:
            names = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    assert "file_reader_files" in names


def test_document_upload_stores_bytes_recoverable_for_reading():  # A-12
    raw = base64.b64decode("aGVsbG8=")
    with client() as c:
        file_id = upload(c, "hello.txt", raw).json()["id"]
        assert c.get(f"{BASE}/files/{file_id}").json()["text"] == "hello"
