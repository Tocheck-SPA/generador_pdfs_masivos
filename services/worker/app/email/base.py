"""Interfaz de envío de correo + composición del mensaje."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Attachment:
    filename: str
    content: bytes
    content_type: str = "application/zip"


@dataclass
class EmailMessage:
    to: list[str]
    subject: str
    html: str
    text: str
    attachments: list[Attachment] = field(default_factory=list)
    reply_to: str | None = None


@dataclass
class EmailResult:
    provider: str
    provider_message_id: str | None
    status: str  # sent | failed
    error_message: str | None = None


class EmailSender(ABC):
    @abstractmethod
    def send(self, message: EmailMessage) -> EmailResult: ...


def build_message(
    *,
    to: list[str],
    company: str,
    form: str,
    date_from: datetime,
    date_to_inclusive: datetime,
    total: int,
    points_count: int,
    download_url: str | None,
    expiration_date: datetime | None,
    attachment: Attachment | None,
    reply_to: str | None,
) -> EmailMessage:
    def d(value: datetime) -> str:
        return value.strftime("%d-%m-%Y")

    subject = f"Informes ToCheck — {company} — {d(date_from)} al {d(date_to_inclusive)}"

    if attachment is not None:
        delivery_line_text = "Los informes se adjuntan en un archivo ZIP."
        delivery_line_html = "Los informes se adjuntan en un archivo ZIP."
    elif download_url:
        delivery_line_text = f"Puede descargar los informes desde el siguiente enlace:\n{download_url}"
        delivery_line_html = f'Puede descargar los informes desde el siguiente enlace:<br><a href="{download_url}">Descargar informes (ZIP)</a>'
    else:
        delivery_line_text = "Los informes están disponibles en la plataforma."
        delivery_line_html = "Los informes están disponibles en la plataforma."

    exp_text = ""
    if expiration_date and not attachment:
        exp_text = f"\n\nEl enlace estará disponible hasta el {d(expiration_date)}."

    text = (
        f"Hola:\n\n"
        f"Se generaron los informes de {form} correspondientes al periodo comprendido "
        f"entre {d(date_from)} y {d(date_to_inclusive)}.\n\n"
        f"Respuestas procesadas: {total}\n"
        f"Puntos de evaluación incluidos: {points_count}\n\n"
        f"{delivery_line_text}{exp_text}\n\n"
        f"Saludos,\nToCheck"
    )

    exp_html = ""
    if expiration_date and not attachment:
        exp_html = f"<p>El enlace estará disponible hasta el <strong>{d(expiration_date)}</strong>.</p>"

    html = f"""\
<div style="font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:#374151;line-height:1.5">
  <p>Hola:</p>
  <p>Se generaron los informes de <strong>{form}</strong> correspondientes al periodo
     comprendido entre <strong>{d(date_from)}</strong> y <strong>{d(date_to_inclusive)}</strong>.</p>
  <p>Respuestas procesadas: <strong>{total}</strong><br>
     Puntos de evaluación incluidos: <strong>{points_count}</strong></p>
  <p>{delivery_line_html}</p>
  {exp_html}
  <p style="color:#64748b">Saludos,<br>ToCheck</p>
</div>"""

    return EmailMessage(
        to=to,
        subject=subject,
        html=html,
        text=text,
        attachments=[attachment] if attachment else [],
        reply_to=reply_to,
    )
