-- ToCheck Reportes — snapshot diario de la fuente MySQL.
-- La ingesta local escribe aquí y web/worker leen desde Neon.

CREATE TABLE IF NOT EXISTS source_sync_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date_from           TIMESTAMP NOT NULL,
    date_to_exclusive    TIMESTAMP NOT NULL,
    status              TEXT NOT NULL DEFAULT 'running',
    responses_seen      INTEGER NOT NULL DEFAULT 0,
    responses_upserted  INTEGER NOT NULL DEFAULT 0,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at        TIMESTAMPTZ,
    error_message       TEXT
);

CREATE TABLE IF NOT EXISTS source_response_snapshots (
    response_id             BIGINT PRIMARY KEY,
    company_id              BIGINT NOT NULL,
    company_name            TEXT,
    company_logo            TEXT,
    form_id                 BIGINT NOT NULL,
    form_name               TEXT,
    form_code               TEXT,
    form_scale              TEXT,
    form_logo               TEXT,
    evaluation_point_id     BIGINT,
    evaluation_point_name   TEXT,
    evaluation_point_address TEXT,
    evaluation_point_country TEXT,
    zone_name               TEXT,
    completed_at            TIMESTAMP NOT NULL,
    payload                 JSONB NOT NULL,
    payload_hash            TEXT NOT NULL,
    sync_run_id             UUID REFERENCES source_sync_runs(id),
    source_synced_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_source_snapshots_filter
    ON source_response_snapshots (company_id, form_id, completed_at);
CREATE INDEX IF NOT EXISTS idx_source_snapshots_point
    ON source_response_snapshots (company_id, form_id, evaluation_point_id, completed_at);
CREATE INDEX IF NOT EXISTS idx_source_snapshots_sync_run
    ON source_response_snapshots (sync_run_id);

CREATE TABLE IF NOT EXISTS source_catalog_companies (
    id          BIGINT PRIMARY KEY,
    name        TEXT NOT NULL,
    logo        TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS source_catalog_forms (
    id          BIGINT PRIMARY KEY,
    company_id  BIGINT NOT NULL,
    name        TEXT NOT NULL,
    code        TEXT,
    scale       TEXT,
    logo        TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_source_forms_company
    ON source_catalog_forms (company_id, name);
