-- Registra dónde se guardó cada artefacto para preservar descargas históricas.
ALTER TABLE report_artifacts
    ADD COLUMN IF NOT EXISTS storage_provider TEXT;

ALTER TABLE report_artifacts
    ADD COLUMN IF NOT EXISTS storage_bucket TEXT;

UPDATE report_artifacts
   SET storage_provider = COALESCE(storage_provider, 'r2')
 WHERE storage_provider IS NULL;

CREATE INDEX IF NOT EXISTS idx_artifacts_storage
    ON report_artifacts (storage_provider, storage_bucket, storage_key);
