import io
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.extensions import db
from app.models.candidate import Candidate
from app.models.document_request import DocumentRequest
from app.services.email_ingestion import EmailIngestionService
from app.services.llm.base import LLMUnavailableError
from app.services.llm.langchain_gemini import LangChainGeminiClient
from app.services.notification import (
    ResendNotificationService,
    SMTPNotificationService,
    get_notification_service,
)

MOCK_PARSE_RESULT = {
    "name": "Priya Sharma",
    "email": "priya.sharma@emaildemo.com",
    "phone": "+91 98765 43210",
    "company": "TechNova Solutions",
    "designation": "Senior Developer",
    "skills": ["Python", "Flask"],
    "confidence": {
        "name": 0.95,
        "email": 0.98,
        "phone": 0.92,
        "company": 0.88,
        "designation": 0.85,
        "skills": 0.9,
    },
}


def _multipart_reply(sender: str, subject: str) -> bytes:
    return (
        f"From: {sender}\r\n".encode()
        + f"Subject: {subject}\r\n".encode()
        + b"Content-Type: multipart/mixed; boundary=\"boundary\"\r\n\r\n"
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


def test_upload_and_parse_flow(client, sample_pdf):
    mock_llm = MagicMock()
    with patch("app.routes.candidates.get_llm_client", return_value=mock_llm), patch(
        "app.routes.candidates.parse_resume_text", return_value=MOCK_PARSE_RESULT
    ):
        data = {"resume": (sample_pdf, "resume.pdf")}
        response = client.post(
            "/candidates/upload",
            data=data,
            content_type="multipart/form-data",
        )

    assert response.status_code == 201
    body = response.get_json()
    assert body["status"] == "parsed"
    assert "id" in body

    candidate = db.session.get(Candidate, body["id"])
    assert candidate.name == "Priya Sharma"
    assert candidate.email == "priya.sharma@emaildemo.com"


def test_document_request_generation(client, sample_pdf):
    mock_llm = MagicMock()
    with patch("app.routes.candidates.get_llm_client", return_value=mock_llm), patch(
        "app.routes.candidates.parse_resume_text", return_value=MOCK_PARSE_RESULT
    ):
        upload = client.post(
            "/candidates/upload",
            data={"resume": (sample_pdf, "resume.pdf")},
            content_type="multipart/form-data",
        )
    candidate_id = upload.get_json()["id"]

    mock_llm = MagicMock()
    mock_llm.complete_json.return_value = {
        "message": "Dear Priya, please share your PAN and Aadhaar for KYC verification."
    }

    with patch("app.routes.candidates.get_llm_client", return_value=mock_llm):
        generate_response = client.post(f"/candidates/{candidate_id}/generate-document-request")

    assert generate_response.status_code == 200
    generated = generate_response.get_json()
    assert "PAN" in generated["message"]
    assert generated["channel"] == "email"

    response = client.post(
        f"/candidates/{candidate_id}/request-documents",
        json={"message": generated["message"], "channel": "email"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["message"].startswith(generated["message"])
    assert f"[Ref: RP-{candidate_id}]" in body["message"]
    assert body["channel"] == "email"

    logged = DocumentRequest.query.filter_by(candidate_id=candidate_id).first()
    assert logged is not None
    assert logged.message == body["message"]


def test_document_request_fallback_when_llm_fails(client, sample_pdf):
    mock_llm = MagicMock()
    with patch("app.routes.candidates.get_llm_client", return_value=mock_llm), patch(
        "app.routes.candidates.parse_resume_text", return_value=MOCK_PARSE_RESULT
    ):
        upload = client.post(
            "/candidates/upload",
            data={"resume": (sample_pdf, "resume.pdf")},
            content_type="multipart/form-data",
        )
    candidate_id = upload.get_json()["id"]

    mock_llm.complete_json.side_effect = LLMUnavailableError("504 Deadline expired")

    with patch("app.routes.candidates.get_llm_client", return_value=mock_llm):
        response = client.post(f"/candidates/{candidate_id}/generate-document-request")

    assert response.status_code == 200
    body = response.get_json()
    assert "PAN" in body["message"]
    assert "Priya Sharma" in body["message"]


def test_submit_documents(client, sample_pdf):
    mock_llm = MagicMock()
    with patch("app.routes.candidates.get_llm_client", return_value=mock_llm), patch(
        "app.routes.candidates.parse_resume_text", return_value=MOCK_PARSE_RESULT
    ):
        upload = client.post(
            "/candidates/upload",
            data={"resume": (sample_pdf, "resume.pdf")},
            content_type="multipart/form-data",
        )
    candidate_id = upload.get_json()["id"]

    pan = (io.BytesIO(b"fake-pan-image"), "pan.png")
    aadhaar = (io.BytesIO(b"fake-aadhaar-image"), "aadhaar.png")

    response = client.post(
        f"/candidates/{candidate_id}/submit-documents",
        data={"pan_document": pan, "aadhaar_document": aadhaar},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "documents_submitted"
    assert body["pan_file"]
    assert body["aadhaar_file"]

    candidate = db.session.get(Candidate, candidate_id)
    assert candidate.status == "documents_submitted"
    assert candidate.pan_path
    assert candidate.aadhaar_path


def test_view_submitted_documents(client, sample_pdf):
    mock_llm = MagicMock()
    with patch("app.routes.candidates.get_llm_client", return_value=mock_llm), patch(
        "app.routes.candidates.parse_resume_text", return_value=MOCK_PARSE_RESULT
    ):
        upload = client.post(
            "/candidates/upload",
            data={"resume": (sample_pdf, "resume.pdf")},
            content_type="multipart/form-data",
        )
    candidate_id = upload.get_json()["id"]

    pan = (io.BytesIO(b"\x89PNG\r\n\x1a\nfake"), "pan.png")
    aadhaar = (io.BytesIO(b"\x89PNG\r\n\x1a\nfake"), "aadhaar.png")
    client.post(
        f"/candidates/{candidate_id}/submit-documents",
        data={"pan_document": pan, "aadhaar_document": aadhaar},
        content_type="multipart/form-data",
    )

    detail = client.get(
        f"/candidates/{candidate_id}",
        headers={"Accept": "application/json"},
    )
    body = detail.get_json()
    assert body["documents"]["pan"]["available"] is True
    assert body["documents"]["aadhaar"]["available"] is True

    pan_resp = client.get(f"/candidates/{candidate_id}/documents/pan")
    assert pan_resp.status_code == 200
    assert pan_resp.mimetype.startswith("image/")


def test_update_candidate_corrects_fields_and_confidence(client, sample_pdf):
    mock_llm = MagicMock()
    with patch("app.routes.candidates.get_llm_client", return_value=mock_llm), patch(
        "app.routes.candidates.parse_resume_text", return_value=MOCK_PARSE_RESULT
    ):
        upload = client.post(
            "/candidates/upload",
            data={"resume": (sample_pdf, "resume.pdf")},
            content_type="multipart/form-data",
        )
    candidate_id = upload.get_json()["id"]

    response = client.patch(
        f"/candidates/{candidate_id}",
        json={"name": "Priya S. Sharma", "skills": ["Python", "Go"]},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["name"] == "Priya S. Sharma"
    assert body["skills"] == ["Python", "Go"]
    assert body["confidence"]["name"] == 1.0
    assert body["confidence"]["skills"] == 1.0
    # Untouched field keeps its original LLM confidence.
    assert body["confidence"]["email"] == 0.98

    invalid = client.patch(f"/candidates/{candidate_id}", json={"skills": "not-a-list"})
    assert invalid.status_code == 400

    empty = client.patch(f"/candidates/{candidate_id}", json={"unknown_field": "x"})
    assert empty.status_code == 400


def test_delete_candidate_removes_record_and_files(client, sample_pdf):
    mock_llm = MagicMock()
    with patch("app.routes.candidates.get_llm_client", return_value=mock_llm), patch(
        "app.routes.candidates.parse_resume_text", return_value=MOCK_PARSE_RESULT
    ):
        upload = client.post(
            "/candidates/upload",
            data={"resume": (sample_pdf, "resume.pdf")},
            content_type="multipart/form-data",
        )
    candidate_id = upload.get_json()["id"]

    pan = (io.BytesIO(b"\x89PNG\r\n\x1a\nfake"), "pan.png")
    aadhaar = (io.BytesIO(b"\x89PNG\r\n\x1a\nfake"), "aadhaar.png")
    client.post(
        f"/candidates/{candidate_id}/submit-documents",
        data={"pan_document": pan, "aadhaar_document": aadhaar},
        content_type="multipart/form-data",
    )

    candidate = db.session.get(Candidate, candidate_id)
    resume_file = Path(candidate.resume_path)
    pan_file = Path(candidate.pan_path)
    assert resume_file.exists()
    assert pan_file.exists()

    response = client.delete(f"/candidates/{candidate_id}")
    assert response.status_code == 200
    assert response.get_json()["status"] == "deleted"

    assert db.session.get(Candidate, candidate_id) is None
    assert not resume_file.exists()
    assert not pan_file.exists()

    missing = client.get(f"/candidates/{candidate_id}", headers={"Accept": "application/json"})
    assert missing.status_code == 404


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


def test_resend_takes_priority_over_smtp():
    config = {
        "RESEND_API_KEY": "re_test_key",
        "SMTP_HOST": "localhost",  # both configured — Resend should win
    }
    assert isinstance(get_notification_service(config), ResendNotificationService)


def test_resend_notification_service_sends():
    service = ResendNotificationService({"RESEND_API_KEY": "re_test_key"})

    mock_response = MagicMock()
    mock_response.read.return_value = b'{"id":"abc"}'
    mock_response.__enter__.return_value = mock_response
    with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
        res = service.send("email", "recipient@test.com", "Hello candidate", "Verification")

    assert res.success is True
    assert res.status == "sent"
    mock_urlopen.assert_called_once()


def test_resend_notification_service_handles_api_error():
    service = ResendNotificationService({"RESEND_API_KEY": "re_test_key"})

    error = urllib.error.HTTPError(
        url="https://api.resend.com/emails",
        code=422,
        msg="Unprocessable",
        hdrs=None,
        fp=io.BytesIO(b'{"message":"invalid recipient"}'),
    )
    with patch("urllib.request.urlopen", side_effect=error):
        res = service.send("email", "recipient@test.com", "Hello", "Subject")

    assert res.success is False
    assert res.status == "failed"
    assert "422" in res.detail


def test_email_ingestion_service(app):
    config = {
        "IMAP_HOST": "imap.test.com",
        "IMAP_PORT": "993",
        "IMAP_USER": "user@test.com",
        "IMAP_PASSWORD": "password",
        "IMAP_USE_SSL": "true",
    }

    with app.app_context():
        candidate = Candidate(
            name="Priya Sharma",
            email="priya@test.com",
            filename="resume.pdf",
            resume_path="resumes/resume.pdf",
            status="parsed",
        )
        db.session.add(candidate)
        db.session.commit()
        candidate_id = candidate.id

    mock_llm = MagicMock()
    mock_llm.complete_json.return_value = {
        "pan_index": 0,
        "aadhaar_index": 1,
        "confidence": 0.95,
    }

    mock_storage = MagicMock()
    mock_storage.save.side_effect = lambda f, folder: f"{folder}/{f.filename}"

    service = EmailIngestionService(config, mock_storage, mock_llm)
    assert service.configured is True

    with patch("imaplib.IMAP4_SSL") as mock_imap_class:
        mock_imap = mock_imap_class.return_value
        mock_imap.search.return_value = ("OK", [b"1"])
        mock_imap.fetch.return_value = (
            "OK",
            [(None, _multipart_reply("priya@test.com", "Re: Document Request"))],
        )

        results = service.poll_inbox()

        assert len(results) == 1
        assert results[0]["status"] == "attached"
        assert results[0]["candidate_id"] == candidate_id
        assert "pan" in results[0]["attached"]
        assert "aadhaar" in results[0]["attached"]

        with app.app_context():
            updated = db.session.get(Candidate, candidate_id)
            assert updated.status == "documents_submitted"
            assert updated.pan_path == f"documents/{candidate_id}/email/pan.png"
            assert updated.aadhaar_path == f"documents/{candidate_id}/email/aadhaar.png"


def test_email_ingestion_disambiguates_same_email_via_reference_tag(app):
    """Two candidates sharing an email must not be confused — the reply's
    reference tag (embedded in the original outbound subject/body) decides
    which candidate row gets the attachment, not email address alone."""
    config = {
        "IMAP_HOST": "imap.test.com",
        "IMAP_PORT": "993",
        "IMAP_USER": "user@test.com",
        "IMAP_PASSWORD": "password",
        "IMAP_USE_SSL": "true",
    }

    with app.app_context():
        c1 = Candidate(name="Amit Kumar", email="amit@test.com", filename="r1.pdf", resume_path="resumes/r1.pdf", status="parsed")
        c2 = Candidate(name="Amit Kumar", email="amit@test.com", filename="r2.pdf", resume_path="resumes/r2.pdf", status="parsed")
        db.session.add_all([c1, c2])
        db.session.commit()
        c1_id, c2_id = c1.id, c2.id

    mock_llm = MagicMock()
    mock_llm.complete_json.return_value = {"pan_index": 0, "aadhaar_index": 1, "confidence": 0.95}
    mock_storage = MagicMock()
    mock_storage.save.side_effect = lambda f, folder: f"{folder}/{f.filename}"

    service = EmailIngestionService(config, mock_storage, mock_llm)

    with patch("imaplib.IMAP4_SSL") as mock_imap_class:
        mock_imap = mock_imap_class.return_value
        mock_imap.search.return_value = ("OK", [b"1"])
        mock_imap.fetch.return_value = (
            "OK",
            [(None, _multipart_reply("amit@test.com", f"Re: Document Request [Ref: RP-{c2_id}]"))],
        )

        results = service.poll_inbox()

    assert len(results) == 1
    assert results[0]["status"] == "attached"
    assert results[0]["candidate_id"] == c2_id

    with app.app_context():
        untouched = db.session.get(Candidate, c1_id)
        updated = db.session.get(Candidate, c2_id)
        assert untouched.status == "parsed"
        assert untouched.pan_path is None
        assert updated.status == "documents_submitted"
        assert updated.pan_path == f"documents/{c2_id}/email/pan.png"


def test_email_ingestion_skips_ambiguous_reply_without_reference_tag(app):
    """Same-email duplicate candidates, but the reply carries no reference tag —
    the service must refuse to guess rather than risk attaching to the wrong one."""
    config = {
        "IMAP_HOST": "imap.test.com",
        "IMAP_PORT": "993",
        "IMAP_USER": "user@test.com",
        "IMAP_PASSWORD": "password",
        "IMAP_USE_SSL": "true",
    }

    with app.app_context():
        c1 = Candidate(name="Amit Kumar", email="amit@test.com", filename="r1.pdf", resume_path="resumes/r1.pdf", status="parsed")
        c2 = Candidate(name="Amit Kumar", email="amit@test.com", filename="r2.pdf", resume_path="resumes/r2.pdf", status="parsed")
        db.session.add_all([c1, c2])
        db.session.commit()
        c1_id, c2_id = c1.id, c2.id

    mock_llm = MagicMock()
    mock_storage = MagicMock()
    service = EmailIngestionService(config, mock_storage, mock_llm)

    with patch("imaplib.IMAP4_SSL") as mock_imap_class:
        mock_imap = mock_imap_class.return_value
        mock_imap.search.return_value = ("OK", [b"1"])
        mock_imap.fetch.return_value = (
            "OK",
            [(None, _multipart_reply("amit@test.com", "Re: Document Request"))],
        )

        results = service.poll_inbox()

    assert len(results) == 1
    assert results[0]["status"] == "ambiguous"
    mock_storage.save.assert_not_called()

    with app.app_context():
        assert db.session.get(Candidate, c1_id).status == "parsed"
        assert db.session.get(Candidate, c2_id).status == "parsed"


def test_sync_inbox_route(client, app):
    with app.app_context():
        candidate = Candidate(
            name="John Doe",
            email="john@test.com",
            filename="resume.pdf",
            resume_path="resumes/resume.pdf",
            status="parsed",
        )
        db.session.add(candidate)
        db.session.commit()

    with patch("app.routes.candidates.get_llm_client") as mock_llm_factory, patch(
        "app.routes.candidates.EmailIngestionService"
    ) as mock_ingestion_class:
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
