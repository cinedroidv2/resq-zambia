from datetime import datetime

from app import db


class OperationalReportAttachment(db.Model):
    """Metadata for a securely stored operational-report attachment."""

    __tablename__ = "operational_report_attachments"

    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(
        db.Integer,
        db.ForeignKey("operational_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False, unique=True)
    mime_type = db.Column(db.String(120), nullable=True)
    size_bytes = db.Column(db.Integer, nullable=False)
    uploaded_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    report = db.relationship("OperationalReport", back_populates="attachments")
    uploaded_by = db.relationship("User", foreign_keys=[uploaded_by_id])

    @staticmethod
    def _timestamp(value):
        return value.isoformat() if value else None

    def to_dict(self):
        return {
            "id": self.id,
            "report_id": self.report_id,
            "original_filename": self.original_filename,
            "mime_type": self.mime_type,
            "size_bytes": int(self.size_bytes or 0),
            "uploaded_by_id": self.uploaded_by_id,
            "uploaded_by": getattr(self.uploaded_by, "username", None),
            "created_at": self._timestamp(self.created_at),
            "download_url": f"/api/operational-report-attachments/{self.id}/download",
        }
