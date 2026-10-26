CREATE TABLE IF NOT EXISTS file_reader_files (
  id TEXT PRIMARY KEY,
  filename TEXT NOT NULL,
  mime TEXT NOT NULL,
  kind TEXT NOT NULL,
  size INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  content BYTEA NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS file_reader_files_created_idx ON file_reader_files (created_at);
