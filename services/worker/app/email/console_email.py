"""Sender de correo por consola (desarrollo/pruebas). No envía nada real."""
from __future__ import annotations

import hashlib

from ..logging_config import get_logger, log_context
from .base import EmailMessage, EmailResult, EmailSender

_log = get_logger("email.console")


class ConsoleEmailSender(EmailSender):
    def send(self, message: EmailMessage) -> EmailResult:
        fake_id = "console-" + hashlib.sha256(
            (message.subject + ",".join(message.to)).encode("utf-8")
        ).hexdigest()[:16]
        log_context(
            _log, 20, "correo simulado (consola)",
            recipients_count=len(message.to),
            subject=message.subject,
            attachments=[a.filename for a in message.attachments],
            attachment_bytes=sum(len(a.content) for a in message.attachments),
        )
        return EmailResult(provider="console", provider_message_id=fake_id, status="sent")
