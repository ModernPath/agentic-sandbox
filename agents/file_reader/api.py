"""HTTP API for the file reader. Routes call service.py only; the rules live there."""

from pathlib import Path

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel, Field

from sandbox_blocks.files import MAX_FILE_BYTES, FileError, UnsupportedFileError
from sandbox_blocks.llm import build_llm
from sandbox_host.errors import AgentInputError, ServiceUnavailable
from sandbox_host.registry import AgentSpec, CliSpec

from . import service
from .store import FileStore
from .tools import build_tools

HERE = Path(__file__).resolve().parent
router = APIRouter()


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class DescribeRequest(BaseModel):
    prompt: str = Field(default="Describe this image.", min_length=1, max_length=1000)


def get_store(request: Request) -> FileStore:
    engine = request.app.state.engine
    if engine is None:
        raise ServiceUnavailable("Storage is not configured. Set DATABASE_URL to use file uploads.")
    return FileStore(engine)


def _llm(request: Request):
    injected = request.app.state.services.get("file_reader", {})
    return injected.get("llm") or build_llm(request.app.state.model_settings)


def _call(action):
    try:
        return action()
    except LookupError as error:
        raise AgentInputError(404, str(error)) from None
    except service.FileTooLargeError as error:
        raise AgentInputError(413, str(error)) from None
    except UnsupportedFileError as error:
        raise AgentInputError(415, str(error)) from None
    except FileError as error:
        raise AgentInputError(422, str(error)) from None
    except ValueError as error:
        raise AgentInputError(422, str(error)) from None


@router.post("/files", status_code=201)
def upload(file: UploadFile = File(...), store: FileStore = Depends(get_store)) -> dict:
    data = file.file.read(MAX_FILE_BYTES + 1)
    return _call(lambda: service.upload_file(store, file.filename or "upload", data))


@router.get("/files")
def list_files(store: FileStore = Depends(get_store)) -> dict:
    return {"files": service.list_files(store)}


@router.get("/files/{file_id}")
def read_file(file_id: str, store: FileStore = Depends(get_store)) -> dict:
    return _call(lambda: service.read_file(store, file_id))


@router.post("/files/{file_id}/describe")
def describe(file_id: str, payload: DescribeRequest, request: Request, store: FileStore = Depends(get_store)) -> dict:
    return _call(lambda: service.describe_image(store, _llm(request), file_id, payload.prompt))


@router.post("/files/{file_id}/ask")
def ask(file_id: str, payload: QuestionRequest, request: Request, store: FileStore = Depends(get_store)) -> dict:
    return _call(lambda: service.ask_file(store, _llm(request), file_id, payload.question))


@router.get("/panel")
def panel_summary(store: FileStore = Depends(get_store)) -> dict:
    return service.summary_panel(store)


def _chat_tools(ctx):
    return build_tools(FileStore(ctx.engine), ctx.llm_or_none())


def _attach(ctx, filename: str, data: bytes) -> dict:
    """The common chat's upload path: the same rules as the upload route."""
    try:
        return service.upload_file(FileStore(ctx.engine), filename, data)
    except service.FileTooLargeError as error:
        raise AgentInputError(413, str(error)) from None
    except UnsupportedFileError as error:
        raise AgentInputError(415, str(error)) from None
    except FileError as error:
        raise AgentInputError(422, str(error)) from None


def make_agent_spec() -> AgentSpec:
    return AgentSpec(
        name="file-reader",
        title="File reader",
        description="Upload CSV, Excel, Word, PowerPoint, PDF, text, JSON, or images, then read them or ask questions.",
        router=router,
        migrations_dir=HERE / "migrations",
        ui_dir=None,
        has_panel=True,
        chat_tools=_chat_tools,
        attach=_attach,
        # upload is not a command: it reads a path on the server. Attachments come through the chat instead.
        cli=CliSpec(module="file_reader.cli", commands=("list", "read", "ask", "describe")),
    )
