from datetime import datetime

from sqlalchemy import event

from app import db


class IncidentAudit(db.Model):
    __tablename__ = "incident_audits"

    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(
        db.Integer,
        db.ForeignKey("incidents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    action = db.Column(db.String(40), nullable=False, index=True)
    previous_status = db.Column(db.String(20), nullable=True, index=True)
    new_status = db.Column(db.String(20), nullable=True, index=True)

    previous_departments = db.Column(db.JSON, nullable=False, default=list)
    new_departments = db.Column(db.JSON, nullable=False, default=list)

    actor_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Snapshots remain readable even when the user account later changes.
    actor_username = db.Column(db.String(64), nullable=True, index=True)
    actor_role = db.Column(db.String(32), nullable=True)

    notes = db.Column(db.Text, nullable=True)
    reporting_channel = db.Column(db.String(10), nullable=True, index=True)
    resolution_details = db.Column(db.Text, nullable=True)

    sms_sent = db.Column(db.Boolean, nullable=True)
    sms_error = db.Column(db.Text, nullable=True)
    details = db.Column(db.JSON, nullable=False, default=dict)

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )

    __table_args__ = (
        db.Index(
            "ix_incident_audits_incident_created",
            "incident_id",
            "created_at",
        ),
    )

    incident = db.relationship("Incident", back_populates="audit_entries")
    actor = db.relationship("User", foreign_keys=[actor_id])

    @staticmethod
    def _timestamp(value):
        return value.isoformat() if value else None

    @staticmethod
    def _department_list(value):
        if not isinstance(value, list):
            return []
        return [str(item).strip().upper() for item in value if str(item).strip()]

    def to_dict(self):
        incident_reference = (
            f"RESQ-{self.incident_id:04d}" if self.incident_id is not None else None
        )
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "incident_reference": incident_reference,
            "action": self.action,
            "previous_status": self.previous_status,
            "new_status": self.new_status,
            "previous_departments": self._department_list(
                self.previous_departments
            ),
            "new_departments": self._department_list(self.new_departments),
            "actor_id": self.actor_id,
            "actor_username": self.actor_username,
            "actor_role": self.actor_role,
            "notes": self.notes,
            "reporting_channel": self.reporting_channel,
            "resolution_details": self.resolution_details,
            "sms_sent": self.sms_sent,
            "sms_error": self.sms_error,
            "details": self.details if isinstance(self.details, dict) else {},
            "created_at": self._timestamp(self.created_at),
        }


@event.listens_for(IncidentAudit, "before_update")
def _prevent_audit_update(mapper, connection, target):
    raise ValueError("Incident audit records are immutable and cannot be updated.")


@event.listens_for(IncidentAudit, "before_delete")
def _prevent_audit_delete(mapper, connection, target):
    raise ValueError("Incident audit records are immutable and cannot be deleted.")
