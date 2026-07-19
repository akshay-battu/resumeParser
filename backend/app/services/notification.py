import logging
import smtplib
from dataclasses import dataclass
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from app.services.net import force_ipv4

logger = logging.getLogger(__name__)


@dataclass
class SendResult:
    success: bool
    status: str  # sent | failed | stub
    detail: str = ""


class NotificationService:
    """Base notification interface."""

    def send(
        self,
        channel: str,
        recipient: str,
        message: str,
        subject: str = "Document Request — ResumeParser KYC",
    ) -> SendResult:
        raise NotImplementedError


class StubNotificationService(NotificationService):
    """Logs instead of sending — used when SMTP is not configured."""

    def send(
        self,
        channel: str,
        recipient: str,
        message: str,
        subject: str = "Document Request — ResumeParser KYC",
    ) -> SendResult:
        logger.info(
            "[NotificationService stub] channel=%s recipient=%s subject=%s message=%s",
            channel,
            recipient,
            subject,
            message[:200],
        )
        return SendResult(
            success=True,
            status="stub",
            detail="SMTP not configured — message logged only",
        )


class SMTPNotificationService(NotificationService):
    """Sends real emails via SMTP."""

    def __init__(self, config):
        self.host = _cfg(config, "SMTP_HOST")
        self.port = int(_cfg(config, "SMTP_PORT", "587"))
        self.user = _cfg(config, "SMTP_USER")
        self.password = _cfg(config, "SMTP_PASSWORD")
        self.from_addr = _cfg(config, "SMTP_FROM") or self.user
        self.from_name = _cfg(config, "SMTP_FROM_NAME")
        use_tls_val = _cfg(config, "SMTP_USE_TLS", True)
        self.use_tls = str(use_tls_val).lower() == "true" if isinstance(use_tls_val, str) else bool(use_tls_val)

    def send(
        self,
        channel: str,
        recipient: str,
        message: str,
        subject: str = "Document Request — ResumeParser KYC",
    ) -> SendResult:
        if channel != "email":
            return SendResult(success=False, status="stub", detail=f"Channel {channel} not supported via SMTP")

        if not recipient:
            return SendResult(success=False, status="failed", detail="No recipient email address")

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = formataddr((self.from_name, self.from_addr)) if self.from_name else self.from_addr
            msg["To"] = recipient
            msg.attach(MIMEText(message, "plain", "utf-8"))

            with force_ipv4(), smtplib.SMTP(self.host, self.port, timeout=30) as server:
                if self.use_tls:
                    server.starttls()
                if self.user and self.password:
                    server.login(self.user, self.password)
                server.sendmail(self.from_addr, [recipient], msg.as_string())

            logger.info("Email sent to %s at %s", recipient, datetime.now(timezone.utc).isoformat())
            return SendResult(success=True, status="sent", detail=f"Email sent to {recipient}")
        except Exception as exc:
            logger.error("SMTP send failed: %s", exc)
            return SendResult(success=False, status="failed", detail=str(exc))


def _cfg(config, key: str, default: str = "") -> str:
    if hasattr(config, "get"):
        return config.get(key, default)
    return getattr(config, key, default)


def get_notification_service(config) -> NotificationService:
    if _cfg(config, "SMTP_HOST"):
        return SMTPNotificationService(config)
    return StubNotificationService()
