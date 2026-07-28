"""Tests del sender Amazon SES."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.email.base import Attachment, EmailMessage
from app.email.ses_email import SesEmailSender
from app.factories import build_email_sender


def test_ses_send_builds_raw_message_and_returns_message_id(monkeypatch):
    client = MagicMock()
    client.send_raw_email.return_value = {"MessageId": "ses-123"}
    monkeypatch.setattr("app.email.ses_email.boto3.client", lambda *a, **k: client)

    sender = SesEmailSender("reportes@tocheck.cl", region="sa-east-1")
    result = sender.send(
        EmailMessage(
            to=["a@example.com", "b@example.com"],
            subject="Informes ToCheck",
            html="<p>hola</p>",
            text="hola",
            attachments=[Attachment(filename="x.zip", content=b"ZIPDATA", content_type="application/zip")],
            reply_to="soporte@tocheck.cl",
        )
    )

    assert result.status == "sent"
    assert result.provider == "ses"
    assert result.provider_message_id == "ses-123"
    kwargs = client.send_raw_email.call_args.kwargs
    assert kwargs["Source"] == "reportes@tocheck.cl"
    assert kwargs["Destinations"] == ["a@example.com", "b@example.com"]
    raw = kwargs["RawMessage"]["Data"]
    assert b"Informes ToCheck" in raw
    assert b"x.zip" in raw
    assert b"ZIPDATA" in raw
    assert b"Reply-To: soporte@tocheck.cl" in raw


def test_ses_send_failure_returns_failed(monkeypatch):
    from botocore.exceptions import ClientError

    client = MagicMock()
    client.send_raw_email.side_effect = ClientError(
        {"Error": {"Code": "MessageRejected", "Message": "no"}},
        "SendRawEmail",
    )
    monkeypatch.setattr("app.email.ses_email.boto3.client", lambda *a, **k: client)

    result = SesEmailSender("reportes@tocheck.cl").send(
        EmailMessage(to=["a@example.com"], subject="s", html="h", text="t")
    )
    assert result.status == "failed"
    assert result.provider == "ses"
    assert result.error_message


def test_build_email_sender_ses(monkeypatch):
    import app.email.ses_email as ses_mod

    monkeypatch.setattr(ses_mod.boto3, "client", lambda *a, **k: MagicMock())
    settings = MagicMock(
        email_backend="ses",
        email_from="reportes@tocheck.cl",
        ses_region="sa-east-1",
        resend_api_key="",
    )
    sender = build_email_sender(settings)
    assert sender.__class__.__name__ == "SesEmailSender"


def test_build_email_sender_rejects_unknown():
    settings = MagicMock(email_backend="mailgun")
    with pytest.raises(ValueError, match="EMAIL_BACKEND"):
        build_email_sender(settings)
