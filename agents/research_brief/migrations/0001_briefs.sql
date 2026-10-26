CREATE TABLE IF NOT EXISTS research_brief_briefs (
  id TEXT PRIMARY KEY,
  topic TEXT NOT NULL,
  summary TEXT,
  sources_json TEXT NOT NULL,
  skipped_json TEXT NOT NULL,
  reason TEXT,
  provider TEXT,
  model TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS research_brief_briefs_created_idx ON research_brief_briefs (created_at);
