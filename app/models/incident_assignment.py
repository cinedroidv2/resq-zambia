from datetime import datetime

from app import db


class IncidentAssignment(db.Model):
    __tablename__ = "incident_assignments"

    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(
        db.Integer,
        db.ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    department = db.Column(db.String(20), nullable=False, index=True)

    active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    assigned_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    assigned_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    removed_at = db.Column(db.DateTime, nullable=True)
    removed_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    incident = db.relationship("Incident", back_populates="assignments")
    assigned_by = db.relationship("User", foreign_keys=[assigned_by_id])
    removed_by = db.relationship("User", foreign_keys=[removed_by_id])

    __table_args__ = (
        db.CheckConstraint(
            "department IN ('POLICE', 'FIRE', 'MEDICAL')",
            name="ck_incident_assignment_department",
        ),
    )

    @staticmethod
    def _timestamp(value):
        return value.isoformat() if value else None

    def to_dict(self):
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "department": self.department,
            "active": bool(self.active),
            "assigned_at": self._timestamp(self.assigned_at),
            "assigned_by_id": self.assigned_by_id,
            "assigned_by": getattr(self.assigned_by, "username", None),
            "removed_at": self._timestamp(self.removed_at),
            "removed_by_id": self.removed_by_id,
            "removed_by": getattr(self.removed_by, "username", None),
        }
