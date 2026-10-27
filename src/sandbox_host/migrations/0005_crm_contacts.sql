CREATE TABLE IF NOT EXISTS crm_contacts (
  id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL,
  name TEXT NOT NULL,
  email TEXT,
  email_key TEXT,
  phone TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL DEFAULT '',
  owner TEXT NOT NULL,
  archived INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (account_id, email_key)
);
CREATE INDEX IF NOT EXISTS crm_contacts_account_idx ON crm_contacts (account_id, archived);
