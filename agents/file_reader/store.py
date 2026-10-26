"""Uploaded file storage in the shared sandbox database (decision: database storage, up to 10 MB)."""

from sqlalchemy import text
from sqlalchemy.engine import Engine

METADATA_COLUMNS = "id, filename, mime, kind, size, sha256, created_at"


class FileStore:
    def __init__(self, engine: Engine):
        self.engine = engine

    def save(self, record: dict) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO file_reader_files (id, filename, mime, kind, size, sha256, content, created_at)"
                     " VALUES (:id, :filename, :mime, :kind, :size, :sha256, :content, :created_at)"),
                record,
            )

    def list_metadata(self, limit: int = 100) -> list[dict]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(f"SELECT {METADATA_COLUMNS} FROM file_reader_files"
                                     " ORDER BY created_at DESC LIMIT :limit"), {"limit": limit})
            return [dict(row._mapping) for row in rows]

    def get_with_content(self, file_id: str) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM file_reader_files WHERE id = :id"), {"id": file_id}).mappings().first()
            return dict(row) if row else None
