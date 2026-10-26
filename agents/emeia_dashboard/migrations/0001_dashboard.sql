CREATE TABLE IF NOT EXISTS emeia_dashboard_targets (
  id TEXT PRIMARY KEY,
  period TEXT NOT NULL,
  objective TEXT NOT NULL,
  key_result TEXT NOT NULL,
  target_value REAL NOT NULL,
  current_value REAL NOT NULL DEFAULT 0,
  unit TEXT NOT NULL DEFAULT '',
  owner TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS emeia_dashboard_targets_period_idx ON emeia_dashboard_targets (period);
CREATE TABLE IF NOT EXISTS emeia_dashboard_wins (
  id TEXT PRIMARY KEY,
  customer TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  value REAL,
  currency TEXT NOT NULL DEFAULT '',
  won_on TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS emeia_dashboard_wins_won_on_idx ON emeia_dashboard_wins (won_on);
CREATE TABLE IF NOT EXISTS emeia_dashboard_market_items (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '',
  source_url TEXT,
  reviewed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS emeia_dashboard_tool_links (
  id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  url TEXT NOT NULL,
  created_at TEXT NOT NULL
);
