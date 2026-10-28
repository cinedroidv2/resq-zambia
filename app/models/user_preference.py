from datetime import datetime

from app import db


class UserPreference(db.Model):
    __tablename__ = "user_preferences"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    theme = db.Column(db.String(12), nullable=False, default="dark")
    auto_refresh_seconds = db.Column(db.Integer, nullable=False, default=10)
    critical_sound_enabled = db.Column(db.Boolean, nullable=False, default=True)
    desktop_notifications_enabled = db.Column(db.Boolean, nullable=False, default=False)
    map_show_incidents = db.Column(db.Boolean, nullable=False, default=True)
    map_show_facilities = db.Column(db.Boolean, nullable=False, default=True)
    map_show_heat = db.Column(db.Boolean, nullable=False, default=True)
    map_cluster_incidents = db.Column(db.Boolean, nullable=False, default=True)
    language = db.Column(db.String(8), nullable=False, default="en")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    user = db.relationship("User", back_populates="preferences")

    __table_args__ = (
        db.CheckConstraint(
            "theme IN ('dark', 'light', 'system')",
            name="ck_user_preferences_theme",
        ),
        db.CheckConstraint(
            "auto_refresh_seconds IN (0, 5, 10, 15, 30, 60)",
            name="ck_user_preferences_refresh",
        ),
        db.CheckConstraint(
            "language IN ('en', 'ny')",
            name="ck_user_preferences_language",
        ),
    )

    def to_dict(self):
        return {
            "theme": self.theme,
            "auto_refresh_seconds": int(self.auto_refresh_seconds or 0),
            "critical_sound_enabled": bool(self.critical_sound_enabled),
            "desktop_notifications_enabled": bool(self.desktop_notifications_enabled),
            "map_show_incidents": bool(self.map_show_incidents),
            "map_show_facilities": bool(self.map_show_facilities),
            "map_show_heat": bool(self.map_show_heat),
            "map_cluster_incidents": bool(self.map_cluster_incidents),
            "language": self.language,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
