import io
from unittest.mock import MagicMock, patch
import pytest

from app.extensions import db
from app.models.candidate import Candidate
from app.services.llm.langchain_gemini import LangChainGeminiClient
from app.services.notification import SMTPNotificationService, get_notification_service
from app.services.email_ingestion import EmailIngestionService


def test_langchain_gemini_client():
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = '{"name": "Test Person", "email": "test@test.com"}'
    mock_llm.invoke.return_value = mock_response

    client = LangChainGeminiClient(api_key="fake-key")
    client.llm = mock_llm

    res = client.complete_json("test prompt", "{}")
    assert res == {"name": "Test Person", "email": "test@test.com"}
    mock_llm.invoke.assert_called_once()


def test_smtp_notification_service():
    config = {
        "SMTP_HOST": "localhost",
        "SMTP_PORT": "1025",
        "SMTP_USER": "user",
        "SMTP_PASSWORD": "password",
        "SMTP_FROM": "from@test.com",
    }
    service = get_notification_service(config)
    assert isinstance(service, SMTPNotificationService)

    with patch("smtplib.SMTP") as mock_smtp:
        instance = mock_smtp.return_value.__enter__.return_value
        res = service.send("email", "recipient@test.com", "Hello candidate", "Verification")
        
        assert res.success is True
        assert res.status == "sent"
        instance.sendmail.assert_called_once()


def test_email_ingestion_service(app):
    config = {
        "IMAP_HOST": "imap.test.com",
        "IMAP_PORT": "993",
        "IMAP_USER": "user@test.com",
        "IMAP_PASSWORD": "password",
        "IMAP_USE_SSL": "true",
    }
    
    # Seed a candidate
    with app.app_context():
        candidate = Candidate(
            name="Priya Sharma",
            email="priya@test.com",
            filename="resume.pdf",
            resume_path="resumes/resume.pdf",
            status="parsed"
        )
        db.session.add(candidate)
        db.session.commit()
        candidate_id = candidate.id

    mock_llm = MagicMock()
    mock_llm.complete_json.return_value = {
        "pan_index": 0,
        "aadhaar_index": 1,
        "confidence": 0.95
    }

    mock_storage = MagicMock()
    mock_storage.save.side_effect = lambda f, folder: f"{folder}/{f.filename}"

    service = EmailIngestionService(config, mock_storage, mock_llm)
    assert service.configured is True

    # Mock IMAP interactions
    with patch("imaplib.IMAP4_SSL") as mock_imap_class:
        mock_imap = mock_imap_class.return_value
        mock_imap.search.return_value = ("OK", [b"1"])
        
        # Raw email with attachments
        raw_email = (
            b"From: priya@test.com\r\n"
            b"Subject: Re: Document Request\r\n"
            b"Content-Type: multipart/mixed; boundary=\"boundary\"\r\n\r\n"
            b"--boundary\r\n"
            b"Content-Type: text/plain\r\n\r\n"
            b"Here are my documents.\r\n"
            b"--boundary\r\n"
            b"Content-Type: image/png\r\n"
            b"Content-Disposition: attachment; filename=\"pan.png\"\r\n\r\n"
            b"fake-pan-data\r\n"
            b"--boundary\r\n"
            b"Content-Type: image/png\r\n"
            b"Content-Disposition: attachment; filename=\"aadhaar.png\"\r\n\r\n"
            b"fake-aadhaar-data\r\n"
            b"--boundary--"
        )
        mock_imap.fetch.return_value = ("OK", [(None, raw_email)])

        results = service.poll_inbox()
        
        assert len(results) == 1
        assert results[0]["status"] == "attached"
        assert results[0]["candidate_id"] == candidate_id
        assert "pan" in results[0]["attached"]
        assert "aadhaar" in results[0]["attached"]

        # Check DB updates
        with app.app_context():
            updated = db.session.get(Candidate, candidate_id)
            assert updated.status == "documents_submitted"
            assert updated.pan_path == f"documents/{candidate_id}/email/pan.png"
            assert updated.aadhaar_path == f"documents/{candidate_id}/email/aadhaar.png"


def test_sync_inbox_route(client, app):
    # Seed candidate
    with app.app_context():
        candidate = Candidate(
            name="John Doe",
            email="john@test.com",
            filename="resume.pdf",
            resume_path="resumes/resume.pdf",
            status="parsed"
        )
        db.session.add(candidate)
        db.session.commit()

    # Route request with mocked services
    with patch("app.routes.candidates.get_llm_client") as mock_llm_factory, \
         patch("app.routes.candidates.EmailIngestionService") as mock_ingestion_class:
        
        mock_llm = MagicMock()
        mock_llm_factory.return_value = mock_llm

        mock_service = mock_ingestion_class.return_value
        mock_service.configured = True
        mock_service.poll_inbox.return_value = [
            {"status": "attached", "candidate_name": "John Doe", "attached": ["pan"]}
        ]

        response = client.post("/candidates/sync-inbox")
        assert response.status_code == 200
        body = response.get_json()
        assert body["processed"] == 1
        assert body["results"][0]["candidate_name"] == "John Doe"
