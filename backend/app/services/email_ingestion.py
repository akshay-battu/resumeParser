import email
import imaplib
import logging
import re
from email.header import decode_header
from io import BytesIO

from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models.candidate import Candidate
from app.services.attachment_classifier import classify_attachments
from app.services.llm.base import LLMClient
from app.services.net import force_ipv4
from app.services.storage import LocalStorageService

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}

# candidates.py sets Reply-To to a plus-addressed variant of the sending mailbox
# (e.g. abattu97+rp1@gmail.com) — invisible in the readable message, but Gmail
# (and most providers) deliver it to the normal inbox while preserving the tag
# in the recipient headers of the reply. Lets a reply be matched back to the
# exact candidate row even when two candidates share the same email address.
PLUS_TAG_RE = re.compile(r"\+rp(\d+)@", re.IGNORECASE)


def _decode_header_value(value: str | None) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


def _extract_email_address(from_header: str) -> str:
    match = re.search(r"[\w.+-]+@[\w.-]+\.\w+", from_header)
    return match.group(0).lower() if match else from_header.lower()


class EmailIngestionService:
    """Poll IMAP inbox for candidate replies and auto-attach identity documents."""

    def __init__(self, config, storage: LocalStorageService, llm: LLMClient):
        self.host = _cfg(config, "IMAP_HOST")
        self.port = int(_cfg(config, "IMAP_PORT", "993"))
        self.user = _cfg(config, "IMAP_USER")
        self.password = _cfg(config, "IMAP_PASSWORD")
        use_ssl_val = _cfg(config, "IMAP_USE_SSL", True)
        self.use_ssl = str(use_ssl_val).lower() == "true" if isinstance(use_ssl_val, str) else bool(use_ssl_val)
        self.storage = storage
        self.llm = llm

    @property
    def configured(self) -> bool:
        return bool(self.host and self.user and self.password)

    def poll_inbox(self) -> list[dict]:
        if not self.configured:
            return [{"status": "skipped", "detail": "IMAP not configured"}]

        candidates = Candidate.query.filter(
            Candidate.email.isnot(None),
            Candidate.status.in_(["parsed", "documents_submitted"]),
        ).all()
        if not candidates:
            return [{"status": "skipped", "detail": "No candidates awaiting documents"}]

        # Group by email — searching once per unique address (rather than once per
        # candidate row) means two candidates sharing an email don't get searched
        # twice, and lets _process_message disambiguate between them by plus-tag.
        by_email: dict[str, list[Candidate]] = {}
        for candidate in candidates:
            by_email.setdefault(candidate.email.lower(), []).append(candidate)

        results = []
        try:
            with force_ipv4():
                if self.use_ssl:
                    mail = imaplib.IMAP4_SSL(self.host, self.port)
                else:
                    mail = imaplib.IMAP4(self.host, self.port)
            mail.login(self.user, self.password)
            mail.select("INBOX")

            for sender_email, candidate_group in by_email.items():
                # Scope the search to this sender address — searching bare UNSEEN
                # would scan the entire inbox (every unread newsletter, etc.), which
                # is slow and can time out on a real mailbox.
                _, data = mail.search(None, "UNSEEN", "FROM", f'"{sender_email}"')
                message_ids = data[0].split() if data[0] else []
                for msg_id in message_ids:
                    result = self._process_message(mail, msg_id, candidate_group)
                    if result:
                        results.append(result)

            mail.logout()
        except Exception as exc:
            logger.error("IMAP poll failed: %s", exc)
            results.append({"status": "error", "detail": str(exc)})

        return results

    def _resolve_candidate(self, candidates: list[Candidate], msg) -> Candidate | None:
        """Pick the exact candidate a reply belongs to.

        Same email address can belong to more than one candidate row, so prefer
        the +rpN plus-address tag carried in the reply's recipient headers (see
        PLUS_TAG_RE above). Only fall back to "the one candidate with this
        email" when it's unambiguous; otherwise refuse to guess.
        """
        for header in ("Delivered-To", "To", "X-Original-To", "Envelope-To"):
            for value in msg.get_all(header, []):
                match = PLUS_TAG_RE.search(_decode_header_value(value))
                if match:
                    target_id = int(match.group(1))
                    return next((c for c in candidates if c.id == target_id), None)

        if len(candidates) == 1:
            return candidates[0]

        return None

    def _process_message(self, mail, msg_id: bytes, candidate_group: list[Candidate]) -> dict | None:
        _, msg_data = mail.fetch(msg_id, "(RFC822)")
        if not msg_data or not msg_data[0]:
            return None

        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)
        sender = _extract_email_address(_decode_header_value(msg.get("From")))

        candidate = self._resolve_candidate(candidate_group, msg)
        if candidate is None:
            mail.store(msg_id, "+FLAGS", "\\Seen")
            return {
                "status": "ambiguous",
                "detail": (
                    f"{len(candidate_group)} candidates share {sender} and no reply-to tag "
                    "was found in the reply — skipped to avoid attaching to the wrong profile"
                ),
            }

        attachments = self._extract_attachments(msg)
        if not attachments:
            mail.store(msg_id, "+FLAGS", "\\Seen")
            return {"status": "ignored", "detail": f"No attachments from {sender}"}

        filenames = [a["filename"] for a in attachments]
        classification = classify_attachments(filenames, self.llm)
        subfolder = f"documents/{candidate.id}/email"
        attached = []

        if classification["pan_index"] is not None:
            idx = classification["pan_index"]
            if 0 <= idx < len(attachments):
                path = self._save_attachment(attachments[idx], subfolder)
                candidate.pan_path = path
                attached.append("pan")

        if classification["aadhaar_index"] is not None:
            idx = classification["aadhaar_index"]
            if 0 <= idx < len(attachments):
                path = self._save_attachment(attachments[idx], subfolder)
                candidate.aadhaar_path = path
                attached.append("aadhaar")

        if attached:
            candidate.status = "documents_submitted"
            db.session.commit()
            mail.store(msg_id, "+FLAGS", "\\Seen")
            return {
                "status": "attached",
                "candidate_id": candidate.id,
                "candidate_name": candidate.name,
                "attached": attached,
                "detail": f"Auto-attached {', '.join(attached)} for {candidate.name}",
            }

        mail.store(msg_id, "+FLAGS", "\\Seen")
        return {"status": "ignored", "detail": f"Could not classify attachments from {sender}"}

    def _extract_attachments(self, msg) -> list[dict]:
        attachments = []
        for part in msg.walk():
            if part.get_content_disposition() != "attachment":
                continue
            filename = _decode_header_value(part.get_filename())
            if not filename:
                continue
            ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            if ext not in ALLOWED_EXTENSIONS:
                continue
            payload = part.get_payload(decode=True)
            if payload:
                attachments.append({"filename": filename, "data": payload})
        return attachments

    def _save_attachment(self, attachment: dict, subfolder: str) -> str:
        file_storage = FileStorage(
            stream=BytesIO(attachment["data"]),
            filename=attachment["filename"],
        )
        return self.storage.save(file_storage, subfolder)


def _cfg(config, key: str, default: str = "") -> str:
    if hasattr(config, "get"):
        return config.get(key, default)
    return getattr(config, key, default)
