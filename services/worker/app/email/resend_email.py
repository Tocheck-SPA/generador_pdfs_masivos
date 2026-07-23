"""Sender de correo vía Resend (producción)."""
from __future__ import annotations

import base64

import httpx

from .base import EmailMessage, EmailResult, EmailSender

_RESEND_ENDPOINT = "https://api.resend.com/emails"


class ResendEmailSender(EmailSender):
    def __init__(self, api_key: str, email_from: str) -> None:
        self._api_key = api_key
        self._from = email_from

    def send(self, message: EmailMessage) -> EmailResult:
        payload: dict[str, object] = {
            "from": self._from,
            "to": message.to,
            "subject": message.subject,
            "html": message.html,
            "text": message.text,
        }
        if message.reply_to:
            payload["reply_to"] = message.reply_to
        if message.attachments:
            payload["attachments"] = [
                {"filename": a.filename, "content": base64.b64encode(a.content).decode("ascii")}
                for a in message.attachments
            ]
        try:
            resp = httpx.post(
                _RESEND_ENDPOINT,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return EmailResult(provider="resend", provider_message_id=data.get("id"), status="sent")
        except httpx.HTTPError as exc:
            return EmailResult(provider="resend", provider_message_id=None, status="failed", error_message=str(exc))
