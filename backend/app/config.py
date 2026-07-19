import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'traqcheck.db'}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "uploads"))
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173")

    # Resend (outbound email over HTTPS — used instead of SMTP when set, since
    # some hosts block outbound SMTP entirely regardless of any client-side fix)
    RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
    RESEND_FROM = os.getenv("RESEND_FROM", "onboarding@resend.dev")

    # SMTP (outbound email)
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM = os.getenv("SMTP_FROM", "")
    SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "ResumeParser Recruiting")
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    # IMAP (inbound email auto-ingest)
    IMAP_HOST = os.getenv("IMAP_HOST", "")
    IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
    IMAP_USER = os.getenv("IMAP_USER", "")
    IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "")
    IMAP_USE_SSL = os.getenv("IMAP_USE_SSL", "true").lower() == "true"
    IMAP_POLL_INTERVAL_SECONDS = int(os.getenv("IMAP_POLL_INTERVAL_SECONDS", "300"))
    IMAP_AUTO_POLL = os.getenv("IMAP_AUTO_POLL", "true").lower() == "true"

    RESUME_EXTENSIONS = {".pdf", ".docx"}
    DOCUMENT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
