from datetime import datetime, timezone
from pathlib import Path

from app.extensions import db


class Candidate(db.Model):
    __tablename__ = "candidates"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    resume_path = db.Column(db.String(512), nullable=False)
    name = db.Column(db.String(255))
    email = db.Column(db.String(255))
    phone = db.Column(db.String(64))
    company = db.Column(db.String(255))
    designation = db.Column(db.String(255))
    skills = db.Column(db.JSON, default=list)
    field_confidence = db.Column(db.JSON, default=dict)
    raw_text = db.Column(db.Text)
    status = db.Column(
        db.String(32),
        nullable=False,
        default="processing",
    )
    pan_path = db.Column(db.String(512))
    aadhaar_path = db.Column(db.String(512))
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    document_requests = db.relationship(
        "DocumentRequest",
        backref="candidate",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def _document_meta(self, doc_type: str, path: str | None) -> dict:
        if not path:
            return {"available": False, "filename": None, "url": None}
        file_path = Path(path)
        display_name = file_path.name.split("_", 1)[-1] if "_" in file_path.name else file_path.name
        return {
            "available": file_path.exists(),
            "filename": display_name,
            "url": f"/candidates/{self.id}/documents/{doc_type}",
        }

    def to_list_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "company": self.company,
            "designation": self.designation,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_detail_dict(self):
        raw_snippet = None
        if self.raw_text:
            raw_snippet = self.raw_text[:500]

        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "company": self.company,
            "designation": self.designation,
            "skills": self.skills or [],
            "confidence": self.field_confidence or {},
            "status": self.status,
            "raw_text_snippet": raw_snippet,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "documents": {
                "resume": self._document_meta("resume", self.resume_path),
                "pan": self._document_meta("pan", self.pan_path),
                "aadhaar": self._document_meta("aadhaar", self.aadhaar_path),
            },
            "document_requests": [
                r.to_dict() for r in sorted(
                    self.document_requests,
                    key=lambda x: x.created_at or datetime.min.replace(tzinfo=timezone.utc),
                    reverse=True,
                )
            ],
        }
