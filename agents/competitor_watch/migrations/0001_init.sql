CREATE TABLE IF NOT EXISTS competitor_watch_competitors (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  name_key TEXT NOT NULL UNIQUE,
  website TEXT,
  note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS competitor_watch_findings (
  id TEXT PRIMARY KEY,
  competitor_id TEXT NOT NULL,
  competitor_name TEXT NOT NULL,
  summary TEXT NOT NULL,
  sources_json TEXT NOT NULL,
  is_error INTEGER NOT NULL DEFAULT 0,
  reviewed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS competitor_watch_findings_created_idx ON competitor_watch_findings (created_at);
