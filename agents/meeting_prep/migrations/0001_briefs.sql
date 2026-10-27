CREATE TABLE IF NOT EXISTS meeting_prep_briefs (
  id TEXT PRIMARY KEY,
  company TEXT NOT NULL,
  website TEXT,
  meeting_date TEXT,
  purpose TEXT NOT NULL DEFAULT '',
  attendees_json TEXT NOT NULL,
  notes_file_json TEXT NOT NULL,
  summary TEXT,
  reason TEXT,
  sources_json TEXT NOT NULL,
  signals_json TEXT NOT NULL,
  gaps_json TEXT NOT NULL,
  provider TEXT,
  model TEXT,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS meeting_prep_briefs_created_idx ON meeting_prep_briefs (created_at);
CREATE INDEX IF NOT EXISTS meeting_prep_briefs_expires_idx ON meeting_prep_briefs (expires_at);
