ALTER TABLE crm_opportunities ADD COLUMN closed_at TEXT;
CREATE INDEX IF NOT EXISTS crm_opportunities_closed_idx ON crm_opportunities (stage, closed_at);
