from datetime import datetime

from app import db


class Facility(db.Model):
    """A mapped Police, Fire or Medical facility used by ResQ."""

    __tablename__ = "facilities"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), nullable=False, unique=True, index=True)
    name = db.Column(db.String(160), nullable=False)
    department = db.Column(db.String(20), nullable=False, index=True)
    readable_location = db.Column(db.String(255), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    coverage_area = db.Column(db.String(255), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    @staticmethod
    def _timestamp(value):
        return value.isoformat() if value else None

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "department": self.department,
            "readable_location": self.readable_location,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "coverage_area": self.coverage_area,
            "active": bool(self.active),
            "created_at": self._timestamp(self.created_at),
            "updated_at": self._timestamp(self.updated_at),
        }
