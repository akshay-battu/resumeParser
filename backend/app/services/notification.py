import json
import logging
import smtplib
import urllib.error
import urllib.request
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


def plus_address(base_email: str, tag: str) -> str:
    """abattu97@gmail.com + 'rp1' -> abattu97+rp1@gmail.com.

    Gmail (and most major providers) deliver plus-addressed mail to the base
    inbox unchanged while preserving the full address in headers — lets a reply
    carry a candidate reference invisibly, with nothing appended to the visible
    subject/body.
    """
    local, _, domain = base_email.partition("@")
    if not domain:
        return base_email
    return f"{local}+{tag}@{domain}"


class NotificationService:
    """Base notification interface."""

    def send(
        self,
        channel: str,
        recipient: str,
        message: str,
        subject: str = "Document Request — ResumeParser KYC",
        candidate_id: int | None = None,
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
        candidate_id: int | None = None,
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
        candidate_id: int | None = None,
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
            if candidate_id is not None:
                msg["Reply-To"] = plus_address(self.from_addr, f"rp{candidate_id}")
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


class SendGridNotificationService(NotificationService):
    """Sends real email via the SendGrid HTTPS API.

    Some hosts (Railway's free/trial tier, notably) block outbound SMTP entirely
    to prevent spam abuse — no client-side fix gets around a platform firewall
    rule. An HTTPS API sidesteps that since port 443 is never blocked.

    Uses SendGrid's Single Sender Verification (verify one email address by
    clicking a link — no domain/DNS ownership needed) rather than full domain
    authentication. Unlike Resend's sandbox mode, this only restricts the *from*
    address — the verified sender can email any recipient, not just themselves.
    """

    def __init__(self, config):
        self.api_key = _cfg(config, "SENDGRID_API_KEY")
        self.from_addr = _cfg(config, "SENDGRID_FROM")
        self.from_name = _cfg(config, "SMTP_FROM_NAME")

    def send(
        self,
        channel: str,
        recipient: str,
        message: str,
        subject: str = "Document Request — ResumeParser KYC",
        candidate_id: int | None = None,
    ) -> SendResult:
        if channel != "email":
            return SendResult(success=False, status="stub", detail=f"Channel {channel} not supported via SendGrid")

        if not recipient:
            return SendResult(success=False, status="failed", detail="No recipient email address")

        from_field = {"email": self.from_addr}
        if self.from_name:
            from_field["name"] = self.from_name

        body = {
            "personalizations": [{"to": [{"email": recipient}]}],
            "from": from_field,
            "subject": subject,
            "content": [{"type": "text/plain", "value": message}],
        }
        if candidate_id is not None:
            body["reply_to"] = {"email": plus_address(self.from_addr, f"rp{candidate_id}")}

        payload = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "ResumeParser/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp.read()
            logger.info("Email sent to %s via SendGrid at %s", recipient, datetime.now(timezone.utc).isoformat())
            return SendResult(success=True, status="sent", detail=f"Email sent to {recipient}")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            logger.error("SendGrid send failed: %s %s", exc.code, body)
            return SendResult(success=False, status="failed", detail=f"SendGrid API error {exc.code}: {body[:200]}")
        except Exception as exc:
            logger.error("SendGrid send failed: %s", exc)
            return SendResult(success=False, status="failed", detail=str(exc))


def _cfg(config, key: str, default: str = "") -> str:
    if hasattr(config, "get"):
        return config.get(key, default)
    return getattr(config, key, default)


def get_notification_service(config) -> NotificationService:
    if _cfg(config, "SENDGRID_API_KEY"):
        return SendGridNotificationService(config)
    if _cfg(config, "SMTP_HOST"):
        return SMTPNotificationService(config)
    return StubNotificationService()
