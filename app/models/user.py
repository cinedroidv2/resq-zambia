from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(32), nullable=False, default="dispatcher", index=True)
    department = db.Column(db.String(32), nullable=True, index=True)
    full_name = db.Column(db.String(120), nullable=True)
    phone_number = db.Column(db.String(30), nullable=True)
    profile_image_filename = db.Column(db.String(255), nullable=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    current_session_started_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    preferences = db.relationship(
        "UserPreference",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def _timestamp(value):
        return value.isoformat() if value else None

    @property
    def display_name(self):
        return str(self.full_name or self.username or "Operator").strip()

    def to_profile_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "full_name": self.full_name,
            "display_name": self.display_name,
            "role": self.role,
            "department": self.department,
            "phone_number": self.phone_number,
            "has_profile_image": bool(self.profile_image_filename),
            "last_login_at": self._timestamp(self.last_login_at),
            "current_session_started_at": self._timestamp(self.current_session_started_at),
            "created_at": self._timestamp(self.created_at),
            "updated_at": self._timestamp(self.updated_at),
        }
