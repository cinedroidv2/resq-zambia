from app import db
from datetime import datetime

class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(db.Integer, db.ForeignKey("incidents.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action_taken = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)