from datetime import datetime

from app import db


class DepartmentResource(db.Model):
    """Operational personnel, vehicles and equipment owned by one department."""

    __tablename__ = "department_resources"

    id = db.Column(db.Integer, primary_key=True)
    department = db.Column(db.String(20), nullable=False, index=True)
    resource_type = db.Column(db.String(20), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    identifier = db.Column(db.String(80), nullable=True, index=True)
    status = db.Column(db.String(20), nullable=False, default="AVAILABLE", index=True)
    details = db.Column(db.Text, nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    facility_id = db.Column(
        db.Integer,
        db.ForeignKey("facilities.id", ondelete="SET NULL"),
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

    facility = db.relationship("Facility", lazy="joined")
    updated_by = db.relationship("User", foreign_keys=[updated_by_id])

    __table_args__ = (
        db.CheckConstraint(
            "department IN ('POLICE', 'FIRE', 'MEDICAL')",
            name="ck_department_resource_department",
        ),
        db.CheckConstraint(
            "resource_type IN ('PERSONNEL', 'VEHICLE', 'EQUIPMENT')",
            name="ck_department_resource_type",
        ),
        db.CheckConstraint(
            "status IN ('AVAILABLE', 'DISPATCHED', 'UNAVAILABLE', 'MAINTENANCE')",
            name="ck_department_resource_status",
        ),
    )

    @staticmethod
    def _timestamp(value):
        return value.isoformat() if value else None

    def to_dict(self):
        return {
            "id": self.id,
            "department": self.department,
            "resource_type": self.resource_type,
            "name": self.name,
            "identifier": self.identifier,
            "status": self.status,
            "details": self.details,
            "active": bool(self.active),
            "facility_id": self.facility_id,
            "facility_name": getattr(self.facility, "name", None),
            "facility_location": getattr(self.facility, "readable_location", None),
            "updated_by_id": self.updated_by_id,
            "updated_by": getattr(self.updated_by, "username", None),
            "created_at": self._timestamp(self.created_at),
            "updated_at": self._timestamp(self.updated_at),
        }
