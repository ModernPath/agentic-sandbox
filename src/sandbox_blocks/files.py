"""Read uploaded files into a normalised DocumentContent.

Limits: 10 MB per file, 50 MB unpacked for Office files, row and character caps.
Images are returned as bytes for the vision path; they are not parsed here.
No macros, external links, or embedded code are executed or followed.
"""

from __future__ import annotations

import csv
import io
import json
import os
import zipfile
from dataclasses import dataclass, field
from typing import Optional

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_UNPACKED_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_ROWS = 500
DEFAULT_MAX_CHARS = 200_000

IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
TEXT_TYPES = {".txt": "text/plain", ".md": "text/markdown"}
OFFICE_KINDS = {".docx": "docx", ".pptx": "pptx", ".xlsx": "xlsx"}


class FileError(ValueError):
    """The file cannot be accepted or read. The message is safe to show."""


class UnsupportedFileError(FileError):
    """The file type is not one the sandbox reads."""


@dataclass
class DocumentContent:
    kind: str
    mime: str
    text: str = ""
    tables: dict = field(default_factory=dict)
    pages: Optional[int] = None
    truncated: bool = False
    image_bytes: Optional[bytes] = None


def read_document(data: bytes, filename: str, *, max_rows: int = DEFAULT_MAX_ROWS,
                  max_chars: int = DEFAULT_MAX_CHARS) -> DocumentContent:
    if len(data) > MAX_FILE_BYTES:
        raise FileError("Files must be 10 MB or smaller")
    ext = os.path.splitext(filename)[1].lower()
    try:
        if ext in IMAGE_TYPES:
            return _image(data, ext)
        if ext == ".pdf":
            return _pdf(data, max_chars)
        if ext in OFFICE_KINDS:
            return _office(data, ext, max_rows, max_chars)
        if ext in (".csv", ".tsv"):
            return _csv(data, ext, max_rows, max_chars)
        if ext == ".json":
            return _json(data, max_chars)
        if ext in TEXT_TYPES:
            return _plain(data, TEXT_TYPES[ext], max_chars)
    except FileError:
        raise
    except Exception as error:  # parser internals must not leak to callers
        raise FileError(f"The {ext or 'file'} could not be read") from error
    raise UnsupportedFileError(f"File type not supported: {ext or 'no extension'}")


def _cap(text: str, max_chars: int) -> tuple[str, bool]:
    return (text[:max_chars], True) if len(text) > max_chars else (text, False)


def _image(data: bytes, ext: str) -> DocumentContent:
    magic = {".png": data[:8] == b"\x89PNG\r\n\x1a\n",
             ".jpg": data[:3] == b"\xff\xd8\xff", ".jpeg": data[:3] == b"\xff\xd8\xff",
             ".webp": data[:4] == b"RIFF" and data[8:12] == b"WEBP"}[ext]
    if not magic:
        raise FileError(f"The content does not match a {ext} image")
    return DocumentContent(kind="image", mime=IMAGE_TYPES[ext], image_bytes=data)


def _pdf(data: bytes, max_chars: int) -> DocumentContent:
    if not data.startswith(b"%PDF"):
        raise FileError("The content does not match a PDF")
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        raise FileError("Password-protected PDFs are not supported")
    text = "\n\n".join((page.extract_text() or "") for page in reader.pages)
    text, truncated = _cap(text, max_chars)
    return DocumentContent(kind="pdf", mime="application/pdf", text=text, pages=len(reader.pages), truncated=truncated)


def _check_zip(data: bytes) -> zipfile.ZipFile:
    if not data.startswith(b"PK"):
        raise FileError("The content does not match an Office document")
    archive = zipfile.ZipFile(io.BytesIO(data))
    unpacked = sum(info.file_size for info in archive.infolist())
    if unpacked > MAX_UNPACKED_BYTES:
        raise FileError("The document is too large when unpacked (limit 50 MB)")
    return archive


def _office(data: bytes, ext: str, max_rows: int, max_chars: int) -> DocumentContent:
    _check_zip(data)
    kind = OFFICE_KINDS[ext]
    mime = {"docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}[kind]
    if kind == "xlsx":
        return _xlsx(data, mime, max_rows, max_chars)
    if kind == "docx":
        return _docx(data, mime, max_chars)
    return _pptx(data, mime, max_chars)


def _xlsx(data: bytes, mime: str, max_rows: int, max_chars: int) -> DocumentContent:
    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    tables, truncated = {}, False
    for sheet in workbook.worksheets:
        rows = []
        for row in sheet.iter_rows(values_only=True):
            if len(rows) == max_rows:
                truncated = True
                break
            rows.append(["" if value is None else str(value) for value in row])
        tables[sheet.title] = rows
    workbook.close()
    return DocumentContent(kind="xlsx", mime=mime, tables=tables, truncated=truncated)


def _docx(data: bytes, mime: str, max_chars: int) -> DocumentContent:
    from docx import Document

    doc = Document(io.BytesIO(data))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text for cell in row.cells))
    text, truncated = _cap("\n".join(parts), max_chars)
    return DocumentContent(kind="docx", mime=mime, text=text, truncated=truncated)


def _pptx(data: bytes, mime: str, max_chars: int) -> DocumentContent:
    from pptx import Presentation

    prs = Presentation(io.BytesIO(data))
    parts = []
    for number, slide in enumerate(prs.slides, start=1):
        parts.append(f"[Slide {number}]")
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text_frame.text.strip():
                parts.append(shape.text_frame.text)
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame is not None:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                parts.append(f"[Notes] {notes}")
    text, truncated = _cap("\n".join(parts), max_chars)
    return DocumentContent(kind="pptx", mime=mime, text=text, pages=len(prs.slides), truncated=truncated)


def _csv(data: bytes, ext: str, max_rows: int, max_chars: int) -> DocumentContent:
    text = data.decode("utf-8-sig")
    delimiter = "\t" if ext == ".tsv" else ","
    rows = []
    truncated = False
    for row in csv.reader(io.StringIO(text), delimiter=delimiter):
        if len(rows) == max_rows:
            truncated = True
            break
        rows.append(row)
    return DocumentContent(kind="csv", mime="text/csv", tables={"csv": rows}, truncated=truncated)


def _json(data: bytes, max_chars: int) -> DocumentContent:
    value = json.loads(data.decode("utf-8-sig"))
    text, truncated = _cap(json.dumps(value, indent=2, ensure_ascii=False), max_chars)
    return DocumentContent(kind="json", mime="application/json", text=text, truncated=truncated)


def _plain(data: bytes, mime: str, max_chars: int) -> DocumentContent:
    text, truncated = _cap(data.decode("utf-8-sig"), max_chars)
    return DocumentContent(kind="text", mime=mime, text=text, truncated=truncated)
