"""Model-callable tools for the file reader. Read-only: uploads are a person's action."""

from __future__ import annotations

from typing import Callable, Optional

from sandbox_blocks.errors import ProviderError
from sandbox_blocks.tools import Tool, tool_from_function

from . import service


def build_tools(store, llm, on_call: Optional[Callable[[str], None]] = None) -> list[Tool]:
    def list_files() -> dict:
        """List uploaded files (name, type, size, upload time), newest first."""
        return _safe(lambda: {"files": service.list_files(store)})

    def read_file(file_id: str) -> dict:
        """Read an uploaded file by its exact id: text (capped), tables for spreadsheets, and page count."""
        return _safe(lambda: service.read_file(store, file_id))

    def ask_file(file_id: str, question: str) -> dict:
        """Answer a question about one uploaded document or image, using only its content."""
        return _safe(lambda: service.ask_file(store, llm, file_id, question))

    def describe_image(file_id: str, prompt: str = "Describe this image.") -> dict:
        """Describe an uploaded image (PNG, JPEG, WebP) by its exact id, following the prompt."""
        return _safe(lambda: service.describe_image(store, llm, file_id, prompt))

    functions = [list_files, read_file, ask_file, describe_image]
    return [tool_from_function(fn, on_call=on_call) for fn in functions]


def _safe(call):
    try:
        return call()
    except ProviderError:
        return {"error": "The model provider failed. Try again later."}
    except (ValueError, LookupError, RuntimeError) as error:
        return {"error": str(error)}
