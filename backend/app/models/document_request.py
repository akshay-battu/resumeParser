from datetime import datetime, timezone

from app.extensions import db


class DocumentRequest(db.Model):
    __tablename__ = "document_requests"

    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(
        db.Integer,
        db.ForeignKey("candidates.id"),
        nullable=False,
    )
    message = db.Column(db.Text, nullable=False)
    channel = db.Column(db.String(32), nullable=False, default="email")
    recipient = db.Column(db.String(255))
    send_status = db.Column(db.String(32), default="pending")
    send_detail = db.Column(db.String(512))
    sent_at = db.Column(db.DateTime)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "candidate_id": self.candidate_id,
            "message": self.message,
            "channel": self.channel,
            "recipient": self.recipient,
            "send_status": self.send_status,
            "send_detail": self.send_detail,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
