"""Sender de correo vía Amazon SES (producción en AWS)."""
from __future__ import annotations

from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from .base import EmailMessage, EmailResult, EmailSender


class SesEmailSender(EmailSender):
    """Envía con la cadena de credenciales por defecto (p. ej. rol de Lambda)."""

    def __init__(self, email_from: str, *, region: str | None = None) -> None:
        self._from = email_from
        self._client = boto3.client("ses", region_name=region or None)

    def send(self, message: EmailMessage) -> EmailResult:
        raw = self._build_raw_message(message)
        try:
            resp = self._client.send_raw_email(
                Source=self._from,
                Destinations=list(message.to),
                RawMessage={"Data": raw},
            )
            return EmailResult(
                provider="ses",
                provider_message_id=resp.get("MessageId"),
                status="sent",
            )
        except (BotoCoreError, ClientError) as exc:
            return EmailResult(
                provider="ses",
                provider_message_id=None,
                status="failed",
                error_message=str(exc),
            )

    def _build_raw_message(self, message: EmailMessage) -> bytes:
        root = MIMEMultipart("mixed")
        root["Subject"] = message.subject
        root["From"] = self._from
        root["To"] = ", ".join(message.to)
        if message.reply_to:
            root["Reply-To"] = message.reply_to

        alternative = MIMEMultipart("alternative")
        alternative.attach(MIMEText(message.text, "plain", "utf-8"))
        alternative.attach(MIMEText(message.html, "html", "utf-8"))
        root.attach(alternative)

        for attachment in message.attachments:
            part = MIMEApplication(attachment.content, _subtype=_subtype(attachment.content_type))
            part.add_header("Content-Disposition", "attachment", filename=attachment.filename)
            if attachment.content_type:
                part.set_type(attachment.content_type)
            root.attach(part)

        return root.as_bytes()


def _subtype(content_type: str) -> str:
    if "/" in content_type:
        return content_type.split("/", 1)[1] or "octet-stream"
    return "octet-stream"
