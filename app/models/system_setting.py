from datetime import datetime

from app import db


class SystemSetting(db.Model):
    __tablename__ = "system_settings"

    id = db.Column(db.Integer, primary_key=True, default=1)
    nlp_confidence_threshold = db.Column(db.Float, nullable=False, default=0.75)
    default_refresh_seconds = db.Column(db.Integer, nullable=False, default=10)
    default_language = db.Column(db.String(8), nullable=False, default="en")
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

    updated_by = db.relationship("User", foreign_keys=[updated_by_id])

    __table_args__ = (
        db.CheckConstraint(
            "nlp_confidence_threshold >= 0.50 AND nlp_confidence_threshold <= 0.95",
            name="ck_system_setting_nlp_threshold",
        ),
        db.CheckConstraint(
            "default_refresh_seconds IN (0, 5, 10, 15, 30, 60)",
            name="ck_system_setting_refresh",
        ),
        db.CheckConstraint(
            "default_language IN ('en', 'ny')",
            name="ck_system_setting_language",
        ),
    )

    def to_dict(self):
        return {
            "nlp_confidence_threshold": float(self.nlp_confidence_threshold or 0.75),
            "default_refresh_seconds": int(self.default_refresh_seconds or 10),
            "default_language": self.default_language,
            "updated_by": getattr(self.updated_by, "username", None),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
