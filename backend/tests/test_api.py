import io
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.extensions import db
from app.models.candidate import Candidate
from app.models.document_request import DocumentRequest
from app.services.llm.base import LLMUnavailableError

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
    assert body["message"] == generated["message"]
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
