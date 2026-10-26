CREATE TABLE IF NOT EXISTS competitor_watch_checks (
  id TEXT PRIMARY KEY,
  competitor_id TEXT NOT NULL,
  outcome TEXT NOT NULL,
  new_signals INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS competitor_watch_checks_competitor_idx ON competitor_watch_checks (competitor_id, created_at);
CREATE TABLE IF NOT EXISTS competitor_watch_signals (
  id TEXT PRIMARY KEY,
  competitor_id TEXT NOT NULL,
  competitor_name TEXT NOT NULL,
  headline TEXT NOT NULL,
  category TEXT NOT NULL,
  importance TEXT NOT NULL,
  summary TEXT NOT NULL,
  source_title TEXT NOT NULL,
  source_url TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new',
  created_at TEXT NOT NULL,
  UNIQUE (competitor_id, source_url)
);
CREATE INDEX IF NOT EXISTS competitor_watch_signals_status_idx ON competitor_watch_signals (status, created_at);
