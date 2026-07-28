"""Configuración del worker vía variables de entorno (Pydantic Settings).

Se valida al iniciar. Los valores por defecto permiten ejecutar el modo `demo`
con fixtures, almacenamiento local y correo por consola, sin credenciales.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# services/worker/app/config.py -> repo root son 3 niveles hacia arriba.
_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # Base operativa (Neon)
    database_url: str = Field(default="", alias="DATABASE_URL")

    # Fuente (ToCheck, solo lectura)
    source_adapter: str = Field(default="fixture", alias="SOURCE_ADAPTER")  # fixture | mysql | postgres | snapshot
    source_database_url: str = Field(default="", alias="SOURCE_DATABASE_URL")
    source_database_sslmode: str = Field(default="require", alias="SOURCE_DATABASE_SSLMODE")
    source_database_use_ssl: bool = Field(default=False, alias="SOURCE_DATABASE_USE_SSL")
    source_database_statement_timeout_seconds: int = Field(
        default=60, alias="SOURCE_DATABASE_STATEMENT_TIMEOUT_SECONDS"
    )
    source_query_batch_size: int = Field(default=100, alias="SOURCE_QUERY_BATCH_SIZE")
    # Base fuente en AWS RDS MySQL (misma convención que otros proyectos ToCheck).
    rds_host: str = Field(default="", alias="RDS_HOST")
    rds_port: int = Field(default=3306, alias="RDS_PORT")
    rds_user: str = Field(default="", alias="RDS_USER")
    rds_pass: str = Field(default="", alias="RDS_PASS")
    rds_db: str = Field(default="", alias="RDS_DB")
    source_company_id: int | None = Field(default=None, alias="SOURCE_COMPANY_ID")
    # Base de imágenes de la fuente (para resolver rutas relativas). Punto de extensión.
    source_asset_base_url: str = Field(
        default="https://tocheck.s3.amazonaws.com", alias="SOURCE_ASSET_BASE_URL"
    )
    # Los logos de empresa se publican en una ruta HTTP distinta a las fotos.
    source_logo_base_url: str = Field(
        default="https://app.tocheck.cl/public/upload/files/logo_empresa",
        alias="SOURCE_LOGO_BASE_URL",
    )
    # Logo oficial de ToCheck, independiente del logo de la empresa auditada.
    tocheck_logo_url: str = Field(
        default="https://app.tocheck.cl/public/img_tocheck/logo_negro.png",
        alias="TOCHECK_LOGO_URL",
    )
    # Directorio local con imágenes por nombre de archivo (fallback offline/pruebas).
    source_asset_local_dir: str = Field(default="", alias="SOURCE_ASSET_LOCAL_DIR")
    fixtures_dir: str = Field(default=str(_REPO_ROOT / "fixtures"), alias="FIXTURES_DIR")

    # Worker
    worker_id: str = Field(default="worker-local-1", alias="WORKER_ID")
    worker_poll_interval_seconds: int = Field(default=5, alias="WORKER_POLL_INTERVAL_SECONDS")
    worker_heartbeat_seconds: int = Field(default=15, alias="WORKER_HEARTBEAT_SECONDS")
    worker_stale_after_seconds: int = Field(default=300, alias="WORKER_STALE_AFTER_SECONDS")
    worker_max_attempts: int = Field(default=3, alias="WORKER_MAX_ATTEMPTS")

    # Almacenamiento
    storage_backend: str = Field(default="local", alias="STORAGE_BACKEND")  # local | r2 | s3
    local_storage_dir: str = Field(default=str(_REPO_ROOT / "services" / "worker" / "output"), alias="LOCAL_STORAGE_DIR")
    r2_account_id: str = Field(default="", alias="R2_ACCOUNT_ID")
    r2_access_key_id: str = Field(default="", alias="R2_ACCESS_KEY_ID")
    r2_secret_access_key: str = Field(default="", alias="R2_SECRET_ACCESS_KEY")
    r2_bucket: str = Field(default="", alias="R2_BUCKET")
    r2_endpoint: str = Field(default="", alias="R2_ENDPOINT")
    r2_region: str = Field(default="auto", alias="R2_REGION")
    s3_bucket: str = Field(default="", alias="AWS_S3_BUCKET")
    s3_region: str = Field(default="us-east-1", alias="AWS_S3_REGION")
    s3_prefix: str = Field(default="reports", alias="AWS_S3_PREFIX")
    s3_endpoint: str = Field(default="", alias="AWS_S3_ENDPOINT")
    report_link_expiration_days: int = Field(default=15, alias="REPORT_LINK_EXPIRATION_DAYS")
    report_retention_days: int = Field(default=90, alias="REPORT_RETENTION_DAYS")

    # Correo
    email_backend: str = Field(default="console", alias="EMAIL_BACKEND")  # console | resend | ses
    resend_api_key: str = Field(default="", alias="RESEND_API_KEY")
    # Región SES (vacío = default de boto3 / AWS_REGION del entorno).
    ses_region: str = Field(default="", alias="SES_REGION")
    email_from: str = Field(default="reportes@tocheck.cl", alias="EMAIL_FROM")
    email_reply_to: str = Field(default="", alias="EMAIL_REPLY_TO")
    max_email_attachment_bytes: int = Field(default=25_000_000, alias="MAX_EMAIL_ATTACHMENT_BYTES")

    # Límites
    max_responses_per_job: int = Field(default=1000, alias="MAX_RESPONSES_PER_JOB")
    max_recipients_per_job: int = Field(default=20, alias="MAX_RECIPIENTS_PER_JOB")
    max_date_range_days: int = Field(default=366, alias="MAX_DATE_RANGE_DAYS")

    # PDF
    pdf_template_version: str = Field(default="1", alias="PDF_TEMPLATE_VERSION")
    pdf_generator_version: str = Field(default="1", alias="PDF_GENERATOR_VERSION")
    pdf_image_max_dimension: int = Field(default=1600, alias="PDF_IMAGE_MAX_DIMENSION")
    pdf_jpeg_quality: int = Field(default=80, alias="PDF_JPEG_QUALITY")
    pdf_render_timeout_seconds: int = Field(default=60, alias="PDF_RENDER_TIMEOUT_SECONDS")
    pdf_max_concurrency: int = Field(default=2, alias="PDF_MAX_CONCURRENCY")

    @property
    def repo_root(self) -> Path:
        return _REPO_ROOT

    @property
    def artifact_storage_bucket(self) -> str | None:
        if self.storage_backend == "r2":
            return self.r2_bucket or None
        if self.storage_backend == "s3":
            return self.s3_bucket or None
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
