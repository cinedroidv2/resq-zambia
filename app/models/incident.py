from datetime import datetime

from app import db


class Incident(db.Model):
    __tablename__ = "incidents"

    id = db.Column(db.Integer, primary_key=True)
    raw_text = db.Column(db.Text, nullable=False)
    channel = db.Column(db.String(10), nullable=False, default="WEB")
    incident_type = db.Column(db.String(20), nullable=True)
    severity = db.Column(db.String(10), nullable=True)

    # Human-readable place name/address, e.g. "Kamwala, Lusaka".
    location = db.Column(db.String(255), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    phone_number = db.Column(db.String(20), nullable=True)
    language = db.Column(db.String(5), nullable=True, default="en")

    status = db.Column(db.String(20), nullable=False, default="Pending")
    dispatcher_notes = db.Column(db.Text, nullable=True)

    nlp_confidence = db.Column(db.Float, nullable=True)
    classification_status = db.Column(db.String(30), nullable=True)

    # Retained for compatibility with older pages while assignments are now
    # stored properly in incident_assignments.
    dispatch_agency = db.Column(db.String(100), nullable=True)
    dispatch_priority = db.Column(db.String(10), nullable=True)
    response_target = db.Column(db.String(50), nullable=True)


    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    dispatched_at = db.Column(db.DateTime, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)

    assignments = db.relationship(
        "IncidentAssignment",
        back_populates="incident",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="IncidentAssignment.assigned_at.asc()",
    )

    audit_entries = db.relationship(
        "IncidentAudit",
        back_populates="incident",
        lazy="select",
        order_by="IncidentAudit.created_at.desc()",
        passive_deletes=True,
    )

    operational_reports = db.relationship(
        "OperationalReport",
        back_populates="incident",
        lazy="selectin",
        order_by="OperationalReport.completed_at.desc()",
        passive_deletes=True,
    )

    @staticmethod
    def _timestamp(value):
        return value.isoformat() if value else None

    def get_active_assignments(self):
        return [assignment for assignment in self.assignments if assignment.active]

    def get_active_departments(self):
        return [assignment.department for assignment in self.get_active_assignments()]

    @property
    def readable_location(self):
        value = str(self.location or "").strip()
        return value or "Readable location not provided"

    def to_dict(self):
        active_assignments = self.get_active_assignments()
        return {
            "id": self.id,
            "reference_id": f"RESQ-{self.id:04d}",
            "raw_text": self.raw_text,
            "channel": self.channel,
            "incident_type": self.incident_type,
            "severity": self.severity,
            "location": self.location,
            "readable_location": self.readable_location,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "phone_number": self.phone_number,
            "language": self.language,
            "status": self.status,
            "dispatcher_notes": self.dispatcher_notes,
            "nlp_confidence": self.nlp_confidence,
            "classification_status": self.classification_status,
            "dispatch_agency": self.dispatch_agency,
            "dispatch_priority": self.dispatch_priority,
            "response_target": self.response_target,
            "assigned_departments": [
                assignment.department for assignment in active_assignments
            ],
            "assignment_records": [
                assignment.to_dict() for assignment in self.assignments
            ],
            "created_at": self._timestamp(self.created_at),
            "updated_at": self._timestamp(self.updated_at),
            "dispatched_at": self._timestamp(self.dispatched_at),
            "resolved_at": self._timestamp(self.resolved_at),
        }
