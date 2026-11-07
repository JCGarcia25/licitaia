"""Notificaciones por correo (SMTP configurable; opcional en el MVP)."""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import get_settings

logger = logging.getLogger("licitaia.notifier")


def send_email(to: str, subject: str, body: str, html_body: str | None = None) -> bool:
    settings = get_settings()
    if not settings.smtp_host:
        logger.info("SMTP no configurado: alerta '%s' se mantiene solo in-app para %s", subject, to)
        return False
    try:
        if html_body:
            msg = MIMEMultipart("alternative")
            msg.attach(MIMEText(body, "plain", "utf-8"))
            msg.attach(MIMEText(html_body, "html", "utf-8"))
        else:
            msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = settings.alerts_from_email
        msg["To"] = to
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.alerts_from_email, [to], msg.as_string())
        return True
    except Exception as exc:
        logger.error("Error enviando correo a %s: %s", to, exc)
        return False
