DROP INDEX IF EXISTS crm_opportunities_closed_idx;
ALTER TABLE crm_opportunities DROP COLUMN closed_at;
