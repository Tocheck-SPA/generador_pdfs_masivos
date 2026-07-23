"""Fábricas que construyen las dependencias (repo/almacenamiento/correo) desde Settings."""
from __future__ import annotations

from .config import Settings
from .email.base import EmailSender
from .email.console_email import ConsoleEmailSender
from .source.fixture_repository import FixtureSourceRepository
from .source.repository import SourceRepository
from .storage.base import Storage
from .storage.local_storage import LocalStorage


def build_source_repository(settings: Settings) -> SourceRepository:
    if settings.source_adapter == "mysql":
        from .source.mysql_repository import MySQLSourceRepository

        return MySQLSourceRepository(settings)
    if settings.source_adapter == "postgres":
        from .source.postgres_repository import PostgresSourceRepository

        return PostgresSourceRepository(settings)
    return FixtureSourceRepository(settings.fixtures_dir)


def build_storage(settings: Settings) -> Storage:
    if settings.storage_backend == "r2":
        from .storage.r2_storage import R2Storage

        return R2Storage(
            account_id=settings.r2_account_id,
            access_key_id=settings.r2_access_key_id,
            secret_access_key=settings.r2_secret_access_key,
            bucket=settings.r2_bucket,
            endpoint=settings.r2_endpoint,
            region=settings.r2_region,
        )
    return LocalStorage(settings.local_storage_dir)


def build_email_sender(settings: Settings) -> EmailSender:
    if settings.email_backend == "resend":
        from .email.resend_email import ResendEmailSender

        return ResendEmailSender(settings.resend_api_key, settings.email_from)
    return ConsoleEmailSender()
