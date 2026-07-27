-- ============================================================
-- ToCheck Reportes — Neon (base operativa)
-- Migración 0001: esquema inicial
-- Solo tablas de la aplicación. NO se copian respuestas de la fuente.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------- Usuarios de la aplicación ----------
CREATE TABLE IF NOT EXISTS app_users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT UNIQUE NOT NULL,
    name          TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ
);

-- ---------- Trabajos de generación ----------
CREATE TABLE IF NOT EXISTS report_jobs (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_by_user_id     UUID REFERENCES app_users(id),
    source_company_id      BIGINT NOT NULL,
    source_company_name    TEXT,
    source_form_id         BIGINT NOT NULL,
    source_form_name       TEXT,
    date_from              TIMESTAMPTZ NOT NULL,
    date_to_exclusive      TIMESTAMPTZ NOT NULL,
    filters                JSONB NOT NULL DEFAULT '{}'::jsonb,
    delivery_mode          TEXT NOT NULL DEFAULT 'auto',
    include_consolidated_pdf BOOLEAN NOT NULL DEFAULT FALSE,
    status                 TEXT NOT NULL DEFAULT 'pending',
    total_responses        INTEGER NOT NULL DEFAULT 0,
    processed_responses    INTEGER NOT NULL DEFAULT 0,
    successful_responses   INTEGER NOT NULL DEFAULT 0,
    failed_responses       INTEGER NOT NULL DEFAULT 0,
    progress_percent       INTEGER NOT NULL DEFAULT 0,
    current_step           TEXT,
    idempotency_key        TEXT UNIQUE,
    attempt_count          INTEGER NOT NULL DEFAULT 0,
    max_attempts           INTEGER NOT NULL DEFAULT 3,
    locked_at              TIMESTAMPTZ,
    locked_by              TEXT,
    heartbeat_at           TIMESTAMPTZ,
    started_at             TIMESTAMPTZ,
    completed_at           TIMESTAMPTZ,
    cancelled_at           TIMESTAMPTZ,
    error_code             TEXT,
    error_message          TEXT,
    warning_message        TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_report_jobs_status      ON report_jobs (status);
CREATE INDEX IF NOT EXISTS idx_report_jobs_created_at  ON report_jobs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_report_jobs_claimable   ON report_jobs (status, heartbeat_at);

-- ---------- Destinatarios ----------
CREATE TABLE IF NOT EXISTS report_job_recipients (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id              UUID NOT NULL REFERENCES report_jobs(id) ON DELETE CASCADE,
    email               TEXT NOT NULL,
    delivery_status     TEXT NOT NULL DEFAULT 'pending',
    provider_message_id TEXT,
    delivered_at        TIMESTAMPTZ,
    error_message       TEXT
);
CREATE INDEX IF NOT EXISTS idx_recipients_job ON report_job_recipients (job_id);

-- ---------- Ítems del trabajo (una fila por respuesta) ----------
CREATE TABLE IF NOT EXISTS report_job_items (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id                      UUID NOT NULL REFERENCES report_jobs(id) ON DELETE CASCADE,
    source_response_id          BIGINT NOT NULL,
    source_response_date        TIMESTAMPTZ,
    source_evaluation_point_id  BIGINT,
    status                      TEXT NOT NULL DEFAULT 'pending',
    attempt_count               INTEGER NOT NULL DEFAULT 0,
    source_payload_hash         TEXT,
    pdf_artifact_id             UUID,
    error_code                  TEXT,
    error_message               TEXT,
    warning_message             TEXT,
    started_at                  TIMESTAMPTZ,
    completed_at                TIMESTAMPTZ,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (job_id, source_response_id)
);
CREATE INDEX IF NOT EXISTS idx_items_job    ON report_job_items (job_id);
CREATE INDEX IF NOT EXISTS idx_items_status ON report_job_items (job_id, status);

-- ---------- Artefactos generados ----------
CREATE TABLE IF NOT EXISTS report_artifacts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id              UUID NOT NULL REFERENCES report_jobs(id) ON DELETE CASCADE,
    source_response_id  BIGINT,
    artifact_type       TEXT NOT NULL,          -- pdf | zip | manifest | consolidated_pdf
    filename            TEXT NOT NULL,
    storage_key         TEXT NOT NULL,
    storage_provider    TEXT NOT NULL DEFAULT 'r2',
    storage_bucket      TEXT,
    content_type        TEXT,
    size_bytes          BIGINT,
    checksum            TEXT,
    source_payload_hash TEXT,
    template_version    TEXT,
    generator_version   TEXT,
    expires_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_artifacts_job  ON report_artifacts (job_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_type ON report_artifacts (job_id, artifact_type);
-- Índice para reutilización de caché de PDF por clave lógica.
CREATE INDEX IF NOT EXISTS idx_artifacts_cache
    ON report_artifacts (source_response_id, source_payload_hash, template_version, generator_version);

-- ---------- Eventos / auditoría ----------
CREATE TABLE IF NOT EXISTS report_events (
    id                 BIGSERIAL PRIMARY KEY,
    job_id             UUID REFERENCES report_jobs(id) ON DELETE CASCADE,
    source_response_id BIGINT,
    level              TEXT NOT NULL DEFAULT 'info',   -- info | warning | error
    event_type         TEXT NOT NULL,
    message            TEXT,
    metadata           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_events_job ON report_events (job_id, created_at);

-- ---------- Entregas de correo ----------
CREATE TABLE IF NOT EXISTS email_deliveries (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id              UUID NOT NULL REFERENCES report_jobs(id) ON DELETE CASCADE,
    provider            TEXT,
    provider_message_id TEXT,
    delivery_mode       TEXT,
    total_size_bytes    BIGINT,
    status              TEXT NOT NULL DEFAULT 'pending',
    idempotency_key     TEXT UNIQUE,
    sent_at             TIMESTAMPTZ,
    error_message       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_email_job ON email_deliveries (job_id);

-- ---------- Caché opcional de catálogos (NO respuestas) ----------
CREATE TABLE IF NOT EXISTS source_catalog_cache (
    id           BIGSERIAL PRIMARY KEY,
    catalog_type TEXT NOT NULL,       -- companies | forms | evaluation_points
    cache_key    TEXT NOT NULL,
    payload      JSONB NOT NULL,
    fetched_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at   TIMESTAMPTZ,
    UNIQUE (catalog_type, cache_key)
);
