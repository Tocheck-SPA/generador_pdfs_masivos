-- La ingesta productiva se limita a una empresa explícita.
ALTER TABLE source_sync_runs
    ADD COLUMN IF NOT EXISTS company_id BIGINT;

CREATE INDEX IF NOT EXISTS idx_source_sync_runs_company
    ON source_sync_runs (company_id, started_at DESC);
