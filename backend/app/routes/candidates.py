import mimetypes
import shutil
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file

from app.extensions import db
from app.models.candidate import Candidate
from app.models.document_request import DocumentRequest
from app.services.document_agent import DocumentRequestAgent
from app.services.email_ingestion import EmailIngestionService
from app.services.llm.base import LLMUnavailableError
from app.services.llm.factory import get_llm_client
from app.services.notification import get_notification_service
from app.services.resume_extractor import ResumeExtractionError, extract_text
from app.services.resume_parser import parse_resume_text
from app.services.storage import (
    LocalStorageService,
    validate_extension,
    validate_file_size,
)
from app.spa import serve_spa, wants_spa

candidates_bp = Blueprint("candidates", __name__)

DOC_TYPE_FIELDS = {
    "pan": "pan_path",
    "aadhaar": "aadhaar_path",
    "resume": "resume_path",
}


def _get_storage() -> LocalStorageService:
    return LocalStorageService(current_app.config["UPLOAD_FOLDER"])


@candidates_bp.route("/upload", methods=["POST"])
def upload_resume():
    if "resume" not in request.files:
        return jsonify({"error": "Missing resume file"}), 400

    file = request.files["resume"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    if not validate_extension(file.filename, current_app.config["RESUME_EXTENSIONS"]):
        return jsonify({"error": "Only PDF and DOCX files are allowed"}), 400

    if not validate_file_size(file, current_app.config["MAX_UPLOAD_MB"]):
        return jsonify({"error": f"File exceeds {current_app.config['MAX_UPLOAD_MB']}MB limit"}), 400

    storage = _get_storage()
    resume_path = storage.save(file, "resumes")

    candidate = Candidate(
        filename=file.filename,
        resume_path=resume_path,
        status="processing",
    )
    db.session.add(candidate)
    db.session.commit()

    try:
        raw_text = extract_text(resume_path)
        candidate.raw_text = raw_text

        if not raw_text.strip():
            candidate.status = "failed"
            db.session.commit()
            return jsonify({"id": candidate.id, "filename": candidate.filename, "status": candidate.status}), 201

        try:
            llm = get_llm_client(current_app.config["LLM_PROVIDER"], current_app.config)
            parsed = parse_resume_text(raw_text, llm)
            candidate.name = parsed.get("name")
            candidate.email = parsed.get("email")
            candidate.phone = parsed.get("phone")
            candidate.company = parsed.get("company")
            candidate.designation = parsed.get("designation")
            candidate.skills = parsed.get("skills", [])
            candidate.field_confidence = parsed.get("confidence", {})
            candidate.status = "parsed" if any(
                [candidate.name, candidate.email, candidate.company]
            ) else "failed"
        except LLMUnavailableError as exc:
            candidate.status = "failed"
            candidate.field_confidence = {"error": str(exc)}

        db.session.commit()
    except ResumeExtractionError as exc:
        candidate.status = "failed"
        candidate.raw_text = str(exc)
        db.session.commit()

    return jsonify({"id": candidate.id, "filename": candidate.filename, "status": candidate.status}), 201


@candidates_bp.route("/sync-inbox", methods=["POST"])
def sync_inbox():
    """Poll IMAP inbox and auto-attach document replies to candidate profiles."""
    try:
        llm = get_llm_client(current_app.config["LLM_PROVIDER"], current_app.config)
    except LLMUnavailableError as exc:
        return jsonify({"error": str(exc), "results": []}), 503

    service = EmailIngestionService(current_app.config, _get_storage(), llm)
    if not service.configured:
        return jsonify({
            "results": [{"status": "skipped", "detail": "IMAP not configured — set IMAP_* env vars"}],
            "processed": 0,
        })

    results = service.poll_inbox()
    attached = sum(1 for r in results if r.get("status") == "attached")
    return jsonify({"results": results, "processed": attached})


@candidates_bp.route("", methods=["GET"])
def list_candidates():
    if wants_spa():
        return serve_spa()

    query = Candidate.query.order_by(Candidate.created_at.desc())
    status = request.args.get("status")
    if status:
        query = query.filter_by(status=status)
    return jsonify([c.to_list_dict() for c in query.all()])


@candidates_bp.route("/<int:candidate_id>", methods=["GET"])
def get_candidate(candidate_id: int):
    if wants_spa():
        return serve_spa()

    candidate = db.session.get(Candidate, candidate_id)
    if not candidate:
        return jsonify({"error": "Candidate not found"}), 404
    return jsonify(candidate.to_detail_dict())


EDITABLE_FIELDS = {"name", "email", "phone", "company", "designation", "skills"}


@candidates_bp.route("/<int:candidate_id>", methods=["PATCH"])
def update_candidate(candidate_id: int):
    candidate = db.session.get(Candidate, candidate_id)
    if not candidate:
        return jsonify({"error": "Candidate not found"}), 404

    body = request.get_json(silent=True) or {}
    updates = {k: v for k, v in body.items() if k in EDITABLE_FIELDS}
    if not updates:
        return jsonify({"error": "No editable fields provided"}), 400

    if "skills" in updates and not isinstance(updates["skills"], list):
        return jsonify({"error": "skills must be a list of strings"}), 400

    confidence = dict(candidate.field_confidence or {})
    for field, value in updates.items():
        setattr(candidate, field, value)
        # Manually corrected fields are as certain as it gets.
        confidence[field] = 1.0
    candidate.field_confidence = confidence

    db.session.commit()
    return jsonify(candidate.to_detail_dict())


@candidates_bp.route("/<int:candidate_id>", methods=["DELETE"])
def delete_candidate(candidate_id: int):
    candidate = db.session.get(Candidate, candidate_id)
    if not candidate:
        return jsonify({"error": "Candidate not found"}), 404

    for path_str in (candidate.resume_path, candidate.pan_path, candidate.aadhaar_path):
        if not path_str:
            continue
        file_path = Path(path_str)
        if file_path.exists():
            file_path.unlink()

    documents_dir = Path(current_app.config["UPLOAD_FOLDER"]).resolve() / "documents" / str(candidate_id)
    if documents_dir.exists():
        shutil.rmtree(documents_dir, ignore_errors=True)

    db.session.delete(candidate)
    db.session.commit()

    return jsonify({"status": "deleted", "id": candidate_id})


@candidates_bp.route("/<int:candidate_id>/documents/<doc_type>", methods=["GET"])
def get_document(candidate_id: int, doc_type: str):
    if doc_type not in DOC_TYPE_FIELDS:
        return jsonify({"error": "Invalid document type. Use pan, aadhaar, or resume."}), 400

    candidate = db.session.get(Candidate, candidate_id)
    if not candidate:
        return jsonify({"error": "Candidate not found"}), 404

    path_str = getattr(candidate, DOC_TYPE_FIELDS[doc_type])
    if not path_str:
        return jsonify({"error": "Document not uploaded"}), 404

    file_path = Path(path_str)
    if not file_path.exists():
        return jsonify({"error": "Document file missing on disk"}), 404

    mimetype = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    return send_file(file_path, mimetype=mimetype)


@candidates_bp.route("/<int:candidate_id>/generate-document-request", methods=["POST"])
def generate_document_request(candidate_id: int):
    """Draft a personalized message for HR to review/edit — does not send anything."""
    candidate = db.session.get(Candidate, candidate_id)
    if not candidate:
        return jsonify({"error": "Candidate not found"}), 404

    if candidate.status not in ("parsed", "documents_submitted"):
        return jsonify({"error": f"Cannot request documents for status: {candidate.status}"}), 400

    channel = request.json.get("channel", "email") if request.is_json else "email"

    try:
        llm = get_llm_client(current_app.config["LLM_PROVIDER"], current_app.config)
        agent = DocumentRequestAgent(llm)
        message = agent.generate_request(
            name=candidate.name,
            email=candidate.email,
            phone=candidate.phone,
            company=candidate.company,
            designation=candidate.designation,
            channel=channel,
        )
    except LLMUnavailableError as exc:
        return jsonify({"error": str(exc), "status": "failed"}), 503

    recipient = candidate.phone if channel == "sms" else (candidate.email or "")

    return jsonify({
        "message": message,
        "channel": channel,
        "recipient": recipient,
    })


@candidates_bp.route("/<int:candidate_id>/request-documents", methods=["POST"])
def request_documents(candidate_id: int):
    """Send a (possibly HR-edited) document request message to the candidate."""
    candidate = db.session.get(Candidate, candidate_id)
    if not candidate:
        return jsonify({"error": "Candidate not found"}), 404

    if candidate.status not in ("parsed", "documents_submitted"):
        return jsonify({"error": f"Cannot request documents for status: {candidate.status}"}), 400

    body = request.get_json(silent=True) or {}
    channel = body.get("channel", "email")
    message = (body.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Message is required — generate or write one before sending"}), 400

    recipient = candidate.phone if channel == "sms" else (candidate.email or "")

    doc_request = DocumentRequest(
        candidate_id=candidate.id,
        message=message,
        channel=channel,
        recipient=recipient,
        send_status="pending",
    )
    db.session.add(doc_request)
    db.session.commit()

    notifier = get_notification_service(current_app.config)
    subject = f"Document Request — {candidate.name or 'Candidate'} KYC Verification"
    send_result = notifier.send(channel, recipient, message, subject=subject)

    from datetime import datetime, timezone

    doc_request.send_status = send_result.status
    doc_request.send_detail = send_result.detail
    if send_result.success and send_result.status == "sent":
        doc_request.sent_at = datetime.now(timezone.utc)
    db.session.commit()

    return jsonify({
        "message": message,
        "channel": channel,
        "recipient": recipient,
        "send_status": send_result.status,
        "send_detail": send_result.detail,
        "created_at": doc_request.created_at.isoformat(),
    })


@candidates_bp.route("/<int:candidate_id>/submit-documents", methods=["POST"])
def submit_documents(candidate_id: int):
    candidate = db.session.get(Candidate, candidate_id)
    if not candidate:
        return jsonify({"error": "Candidate not found"}), 404

    if "pan_document" not in request.files or "aadhaar_document" not in request.files:
        return jsonify({"error": "Both pan_document and aadhaar_document are required"}), 400

    pan_file = request.files["pan_document"]
    aadhaar_file = request.files["aadhaar_document"]
    allowed = current_app.config["DOCUMENT_EXTENSIONS"]
    max_mb = current_app.config["MAX_UPLOAD_MB"]

    for label, f in [("pan_document", pan_file), ("aadhaar_document", aadhaar_file)]:
        if not f.filename:
            return jsonify({"error": f"Missing file for {label}"}), 400
        if not validate_extension(f.filename, allowed):
            return jsonify({"error": f"{label}: only JPG, PNG, and PDF allowed"}), 400
        if not validate_file_size(f, max_mb):
            return jsonify({"error": f"{label} exceeds {max_mb}MB limit"}), 400

    storage = _get_storage()
    subfolder = f"documents/{candidate_id}"
    candidate.pan_path = storage.save(pan_file, subfolder)
    candidate.aadhaar_path = storage.save(aadhaar_file, subfolder)
    candidate.status = "documents_submitted"
    db.session.commit()

    return jsonify({
        "status": candidate.status,
        "pan_file": candidate.pan_path,
        "aadhaar_file": candidate.aadhaar_path,
        "documents": candidate.to_detail_dict()["documents"],
    })
