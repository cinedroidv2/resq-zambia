from datetime import datetime

from app import db


class OperationalReport(db.Model):
    """Formal post-dispatch report for one responding department."""

    __tablename__ = "operational_reports"

    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(
        db.Integer,
        db.ForeignKey("incidents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    department = db.Column(db.String(20), nullable=False, index=True)

    responder_name = db.Column(db.String(160), nullable=False)
    findings = db.Column(db.Text, nullable=False)
    actions_taken = db.Column(db.Text, nullable=False)
    outcome = db.Column(db.Text, nullable=False)
    people_affected = db.Column(db.Integer, nullable=False, default=0)
    resources_used = db.Column(db.Text, nullable=True)

    final_classification = db.Column(db.String(20), nullable=False)
    final_departments = db.Column(db.JSON, nullable=False, default=list)
    completed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    updated_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    incident = db.relationship("Incident", back_populates="operational_reports")
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    updated_by = db.relationship("User", foreign_keys=[updated_by_id])
    attachments = db.relationship(
        "OperationalReportAttachment",
        back_populates="report",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="OperationalReportAttachment.created_at.asc()",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "incident_id",
            "department",
            name="uq_operational_report_incident_department",
        ),
        db.CheckConstraint(
            "department IN ('POLICE', 'FIRE', 'MEDICAL')",
            name="ck_operational_report_department",
        ),
        db.CheckConstraint(
            "final_classification IN ('MEDICAL', 'FIRE', 'CRIME')",
            name="ck_operational_report_final_classification",
        ),
        db.CheckConstraint(
            "people_affected >= 0",
            name="ck_operational_report_people_affected",
        ),
    )

    @staticmethod
    def _timestamp(value):
        return value.isoformat() if value else None

    @staticmethod
    def _departments(value):
        if not isinstance(value, list):
            return []
        allowed = {"POLICE", "FIRE", "MEDICAL"}
        output = []
        for item in value:
            department = str(item or "").strip().upper()
            if department in allowed and department not in output:
                output.append(department)
        return output

    def to_dict(self):
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "incident_reference": (
                f"RESQ-{self.incident_id:04d}" if self.incident_id is not None else None
            ),
            "department": self.department,
            "responder_name": self.responder_name,
            "findings": self.findings,
            "actions_taken": self.actions_taken,
            "outcome": self.outcome,
            "people_affected": int(self.people_affected or 0),
            "resources_used": self.resources_used,
            "final_classification": self.final_classification,
            "final_departments": self._departments(self.final_departments),
            "completed_at": self._timestamp(self.completed_at),
            "created_by_id": self.created_by_id,
            "created_by": getattr(self.created_by, "username", None),
            "updated_by_id": self.updated_by_id,
            "updated_by": getattr(self.updated_by, "username", None),
            "created_at": self._timestamp(self.created_at),
            "updated_at": self._timestamp(self.updated_at),
            "attachments": [item.to_dict() for item in self.attachments],
        }
