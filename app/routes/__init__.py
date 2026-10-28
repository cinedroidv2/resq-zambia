from datetime import datetime, timedelta
from math import atan2, cos, radians, sin, sqrt
import os
from uuid import uuid4

from flask import (
    Blueprint, current_app, jsonify, redirect, render_template, request,
    send_from_directory, url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import or_
from sqlalchemy.orm import selectinload
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from app import db, socketio
from app.models.incident import Incident
from app.models.incident_assignment import IncidentAssignment
from app.models.incident_audit import IncidentAudit
from app.models.facility import Facility
from app.models.department_resource import DepartmentResource
from app.models.operational_report import OperationalReport
from app.models.operational_report_attachment import OperationalReportAttachment
from app.models.user_preference import UserPreference
from app.models.system_setting import SystemSetting
from app.services.sms_service import send_help_is_coming_sms

main = Blueprint("main", __name__)

ALLOWED_TYPES = {"MEDICAL", "FIRE", "CRIME"}
ALLOWED_SEVERITIES = {"LOW", "HIGH", "CRITICAL"}
ALLOWED_DEPARTMENTS = {"POLICE", "FIRE", "MEDICAL"}
ROLE_DEPARTMENT = {
    "police": "POLICE",
    "fire": "FIRE",
    "medical": "MEDICAL",
}

INCIDENT_TYPE_DEFAULT_DEPARTMENTS = {
    "CRIME": ["POLICE"],
    "FIRE": ["FIRE"],
    "MEDICAL": ["MEDICAL"],
}


def _default_departments_for_incident_type(incident_type):
    incident_type = str(incident_type or "").strip().upper()
    return list(INCIDENT_TYPE_DEFAULT_DEPARTMENTS.get(incident_type, []))
DEFAULT_NLP_CONFIDENCE_THRESHOLD = 0.75
RESOURCE_TYPES = {"PERSONNEL", "VEHICLE", "EQUIPMENT"}
RESOURCE_STATUSES = {"AVAILABLE", "DISPATCHED", "UNAVAILABLE", "MAINTENANCE"}
OPERATIONAL_REPORT_STATUSES = {"DISPATCHED", "ESCALATED", "RESOLVED"}
ALLOWED_ATTACHMENT_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "webp", "txt", "doc", "docx"}
MAX_OPERATIONAL_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_OPERATIONAL_ATTACHMENTS = 5
ALLOWED_PROFILE_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_PROFILE_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_THEMES = {"dark", "light", "system"}
ALLOWED_REFRESH_SECONDS = {0, 5, 10, 15, 30, 60}
ALLOWED_LANGUAGES = {"en", "ny"}


def _actor_snapshot(actor=None):
    actor = actor if actor is not None else current_user
    if not getattr(actor, "is_authenticated", False):
        return None, None, None
    return (
        getattr(actor, "id", None),
        str(getattr(actor, "username", "") or "").strip() or None,
        str(getattr(actor, "role", "") or "").strip().lower() or None,
    )


def _create_audit(
    incident,
    action,
    *,
    previous_status=None,
    new_status=None,
    previous_departments=None,
    new_departments=None,
    notes=None,
    resolution_details=None,
    sms_sent=None,
    sms_error=None,
    details=None,
    actor=None,
):
    """Add one immutable audit record to the current database transaction."""
    actor_id, actor_username, actor_role = _actor_snapshot(actor)
    audit = IncidentAudit(
        incident_id=incident.id,
        action=str(action or "UNKNOWN").strip().upper(),
        previous_status=(str(previous_status).strip().title() if previous_status else None),
        new_status=str(new_status).strip().title() if new_status else None,
        previous_departments=sorted(set(previous_departments or [])),
        new_departments=sorted(set(new_departments or [])),
        actor_id=actor_id,
        actor_username=actor_username,
        actor_role=actor_role,
        notes=str(notes).strip() if notes else None,
        reporting_channel=str(incident.channel or "").strip().upper() or None,
        resolution_details=(str(resolution_details).strip() if resolution_details else None),
        sms_sent=sms_sent,
        sms_error=str(sms_error).strip() if sms_error else None,
        details=details if isinstance(details, dict) else {},
        created_at=datetime.utcnow(),
    )
    db.session.add(audit)
    return audit


def _emit_audit(audit):
    if audit is not None:
        socketio.emit("audit_log_created", {"audit_id": audit.id})


def _audit_visible_to_current_user(audit):
    role = str(getattr(current_user, "role", "") or "").lower()
    if role in {"admin", "dispatcher"}:
        return True

    required_department = ROLE_DEPARTMENT.get(role)
    if not required_department:
        return False

    historical_departments = set(audit.previous_departments or []) | set(audit.new_departments or [])
    if required_department in historical_departments:
        return True

    incident = getattr(audit, "incident", None)
    return bool(incident and required_department in _active_department_names(incident))


def _parse_audit_date(value, *, end_of_day=False):
    value = str(value or "").strip()
    if not value:
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None
    return parsed + timedelta(days=1) if end_of_day else parsed

# Stage 4 stores the shared operational map facilities in the database.
# These defaults initialise an empty prototype database; administrators can
# replace them with formally verified departmental records during deployment.
DEFAULT_FACILITIES = (
    {
        "code": "police-central",
        "name": "Lusaka Central Police Station",
        "department": "POLICE",
        "readable_location": "Central Lusaka",
        "latitude": -15.4100,
        "longitude": 28.2900,
        "coverage_area": "Lusaka CBD and surrounding central districts",
    },
    {
        "code": "police-woodlands",
        "name": "Woodlands Police Station",
        "department": "POLICE",
        "readable_location": "Woodlands, Lusaka",
        "latitude": -15.4387,
        "longitude": 28.3495,
        "coverage_area": "Woodlands and nearby residential districts",
    },
    {
        "code": "police-kabwata",
        "name": "Kabwata Police Station",
        "department": "POLICE",
        "readable_location": "Kabwata, Lusaka",
        "latitude": -15.4255,
        "longitude": 28.3098,
        "coverage_area": "Kabwata and adjacent communities",
    },
    {
        "code": "police-matero",
        "name": "Matero Police Station",
        "department": "POLICE",
        "readable_location": "Matero, Lusaka",
        "latitude": -15.3658,
        "longitude": 28.2588,
        "coverage_area": "Matero and north-western Lusaka",
    },
    {
        "code": "fire-central",
        "name": "Lusaka Central Fire Station",
        "department": "FIRE",
        "readable_location": "Central Lusaka",
        "latitude": -15.4083,
        "longitude": 28.2917,
        "coverage_area": "Central Lusaka and adjoining districts",
    },
    {
        "code": "fire-kabwata",
        "name": "Kabwata Fire Station",
        "department": "FIRE",
        "readable_location": "Kabwata, Lusaka",
        "latitude": -15.4268,
        "longitude": 28.3092,
        "coverage_area": "Kabwata and southern Lusaka",
    },
    {
        "code": "fire-matero",
        "name": "Matero Fire Station",
        "department": "FIRE",
        "readable_location": "Matero, Lusaka",
        "latitude": -15.3669,
        "longitude": 28.2634,
        "coverage_area": "Matero and north-western Lusaka",
    },
    {
        "code": "medical-uth",
        "name": "University Teaching Hospital",
        "department": "MEDICAL",
        "readable_location": "Nationalist Road, Lusaka",
        "latitude": -15.3967,
        "longitude": 28.3336,
        "coverage_area": "Lusaka metropolitan referral coverage",
    },
    {
        "code": "medical-matero",
        "name": "Matero Level One Hospital",
        "department": "MEDICAL",
        "readable_location": "Matero, Lusaka",
        "latitude": -15.3689,
        "longitude": 28.2578,
        "coverage_area": "Matero and surrounding communities",
    },
    {
        "code": "medical-chilenje",
        "name": "Chilenje Level One Hospital",
        "department": "MEDICAL",
        "readable_location": "Chilenje, Lusaka",
        "latitude": -15.4375,
        "longitude": 28.3278,
        "coverage_area": "Chilenje and southern Lusaka",
    },
    {
        "code": "medical-levy-mwanawasa",
        "name": "Levy Mwanawasa University Teaching Hospital",
        "department": "MEDICAL",
        "readable_location": "Great East Road, Lusaka",
        "latitude": -15.3563,
        "longitude": 28.3904,
        "coverage_area": "Eastern Lusaka and national referral coverage",
    },
)


# Prototype-only operational resources. These are inserted once, only when the
# identifier is missing, and can then be edited through the dashboard.
DEMO_DEPARTMENT_RESOURCES = (
    {"department": "POLICE", "resource_type": "PERSONNEL", "name": "Inspector Chanda", "identifier": "POL-P-001", "status": "AVAILABLE", "facility_code": "police-central", "details": "Shift supervisor - demo record"},
    {"department": "POLICE", "resource_type": "PERSONNEL", "name": "Officer Mulenga", "identifier": "POL-P-014", "status": "DISPATCHED", "facility_code": "police-kabwata", "details": "Patrol officer - demo record"},
    {"department": "POLICE", "resource_type": "PERSONNEL", "name": "Officer Phiri", "identifier": "POL-P-022", "status": "AVAILABLE", "facility_code": "police-woodlands", "details": "Response officer - demo record"},
    {"department": "POLICE", "resource_type": "VEHICLE", "name": "Patrol Unit 01", "identifier": "POL-V-001", "status": "AVAILABLE", "facility_code": "police-central", "details": "Marked response vehicle - demo record"},
    {"department": "POLICE", "resource_type": "VEHICLE", "name": "Patrol Unit 07", "identifier": "POL-V-007", "status": "MAINTENANCE", "facility_code": "police-kabwata", "details": "Marked patrol vehicle - demo record"},
    {"department": "POLICE", "resource_type": "EQUIPMENT", "name": "Radio Kit Alpha", "identifier": "POL-E-001", "status": "AVAILABLE", "facility_code": "police-central", "details": "Portable radio set - demo record"},

    {"department": "FIRE", "resource_type": "PERSONNEL", "name": "Station Officer Banda", "identifier": "FIR-P-001", "status": "AVAILABLE", "facility_code": "fire-central", "details": "Station lead - demo record"},
    {"department": "FIRE", "resource_type": "PERSONNEL", "name": "Firefighter Tembo", "identifier": "FIR-P-012", "status": "DISPATCHED", "facility_code": "fire-kabwata", "details": "Response crew - demo record"},
    {"department": "FIRE", "resource_type": "PERSONNEL", "name": "Firefighter Mwewa", "identifier": "FIR-P-018", "status": "AVAILABLE", "facility_code": "fire-matero", "details": "Rescue crew - demo record"},
    {"department": "FIRE", "resource_type": "VEHICLE", "name": "Fire Engine 1", "identifier": "FIR-V-001", "status": "AVAILABLE", "facility_code": "fire-central", "details": "Primary response engine - demo record"},
    {"department": "FIRE", "resource_type": "VEHICLE", "name": "Fire Engine 4", "identifier": "FIR-V-004", "status": "MAINTENANCE", "facility_code": "fire-matero", "details": "Response engine - demo record"},
    {"department": "FIRE", "resource_type": "EQUIPMENT", "name": "Rescue Gear Set A", "identifier": "FIR-E-001", "status": "AVAILABLE", "facility_code": "fire-central", "details": "Breathing and extraction equipment - demo record"},

    {"department": "MEDICAL", "resource_type": "PERSONNEL", "name": "Paramedic Zulu", "identifier": "MED-P-001", "status": "AVAILABLE", "facility_code": "medical-uth", "details": "Advanced life support - demo record"},
    {"department": "MEDICAL", "resource_type": "PERSONNEL", "name": "EMT Lungu", "identifier": "MED-P-008", "status": "DISPATCHED", "facility_code": "medical-chilenje", "details": "Emergency medical technician - demo record"},
    {"department": "MEDICAL", "resource_type": "PERSONNEL", "name": "Nurse Mwila", "identifier": "MED-P-014", "status": "AVAILABLE", "facility_code": "medical-matero", "details": "Emergency response nurse - demo record"},
    {"department": "MEDICAL", "resource_type": "VEHICLE", "name": "Ambulance 3", "identifier": "MED-V-003", "status": "AVAILABLE", "facility_code": "medical-uth", "details": "Advanced life support ambulance - demo record"},
    {"department": "MEDICAL", "resource_type": "VEHICLE", "name": "Ambulance 6", "identifier": "MED-V-006", "status": "UNAVAILABLE", "facility_code": "medical-chilenje", "details": "Emergency ambulance - demo record"},
    {"department": "MEDICAL", "resource_type": "EQUIPMENT", "name": "Trauma Kit A", "identifier": "MED-E-001", "status": "AVAILABLE", "facility_code": "medical-uth", "details": "Trauma stabilisation equipment - demo record"},
)


def _ensure_default_facilities():
    """Seed only missing facility codes without overwriting edited records."""
    existing_codes = {
        code for (code,) in db.session.query(Facility.code).all()
    }
    created = False
    for item in DEFAULT_FACILITIES:
        if item["code"] in existing_codes:
            continue
        db.session.add(Facility(**item))
        created = True
    if created:
        db.session.commit()



def _ensure_demo_department_resources():
    """Insert missing prototype resources without overwriting edited records."""
    _ensure_default_facilities()
    facilities_by_code = {
        facility.code: facility
        for facility in Facility.query.filter(Facility.active.is_(True)).all()
    }
    existing_identifiers = {
        identifier
        for (identifier,) in db.session.query(DepartmentResource.identifier)
        .filter(DepartmentResource.identifier.isnot(None)).all()
    }
    created = False
    for item in DEMO_DEPARTMENT_RESOURCES:
        if item["identifier"] in existing_identifiers:
            continue
        facility = facilities_by_code.get(item.get("facility_code"))
        db.session.add(DepartmentResource(
            department=item["department"],
            resource_type=item["resource_type"],
            name=item["name"],
            identifier=item["identifier"],
            status=item["status"],
            details=item.get("details"),
            active=True,
            facility_id=facility.id if facility else None,
            updated_by_id=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ))
        created = True
    if created:
        db.session.commit()



def _system_settings():
    settings = SystemSetting.query.get(1)
    if settings is None:
        settings = SystemSetting(
            id=1,
            nlp_confidence_threshold=DEFAULT_NLP_CONFIDENCE_THRESHOLD,
            default_refresh_seconds=10,
            default_language="en",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.session.add(settings)
        db.session.commit()
    return settings


def _nlp_confidence_threshold():
    settings = _system_settings()
    value = float(settings.nlp_confidence_threshold or DEFAULT_NLP_CONFIDENCE_THRESHOLD)
    return min(0.95, max(0.50, value))


def _user_preferences(user):
    preference = UserPreference.query.filter_by(user_id=user.id).first()
    if preference is None:
        system = _system_settings()
        preference = UserPreference(
            user_id=user.id,
            theme="dark",
            auto_refresh_seconds=int(system.default_refresh_seconds or 10),
            critical_sound_enabled=True,
            desktop_notifications_enabled=False,
            map_show_incidents=True,
            map_show_facilities=True,
            map_show_heat=True,
            map_cluster_incidents=True,
            language=str(system.default_language or "en"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.session.add(preference)
        db.session.commit()
    return preference


def _profile_image_directory():
    directory = os.path.join(current_app.instance_path, "uploads", "profile_images")
    os.makedirs(directory, exist_ok=True)
    return directory


def _profile_metrics(user):
    audits = IncidentAudit.query.filter(
        IncidentAudit.actor_id == user.id,
    ).order_by(IncidentAudit.created_at.asc()).all()

    review_actions = {
        "NOTE_ADDED", "NOTE_UPDATED", "NOTE_CLEARED",
        "CLASSIFICATION_CORRECTED", "CLASSIFICATION_CONFIRMED",
        "ASSIGNMENT_UPDATED", "DISPATCHED", "ESCALATED", "RESOLVED",
        "OPERATIONAL_REPORT_SAVED", "REPORT_ATTACHMENT_UPLOADED",
    }
    reviewed_ids = {
        item.incident_id for item in audits
        if item.incident_id is not None and item.action in review_actions
    }
    dispatched_ids = {
        item.incident_id for item in audits
        if item.incident_id is not None and item.action in {"DISPATCHED", "ESCALATED"}
    }

    reports = OperationalReport.query.filter(
        OperationalReport.created_by_id == user.id,
    ).all()
    handled_ids = dispatched_ids | {
        item.incident_id for item in reports if item.incident_id is not None
    }

    first_review_by_incident = {}
    for item in audits:
        if item.incident_id is None or item.action not in review_actions:
            continue
        first_review_by_incident.setdefault(item.incident_id, item.created_at)

    review_seconds = []
    if first_review_by_incident:
        incident_rows = Incident.query.filter(
            Incident.id.in_(list(first_review_by_incident.keys()))
        ).all()
        for incident in incident_rows:
            reviewed_at = first_review_by_incident.get(incident.id)
            if incident.created_at and reviewed_at and reviewed_at >= incident.created_at:
                review_seconds.append((reviewed_at - incident.created_at).total_seconds())

    role = str(user.role or "").strip().lower()
    department = str(user.department or ROLE_DEPARTMENT.get(role) or "").strip().upper()
    if department in ALLOWED_DEPARTMENTS:
        active_case_count = IncidentAssignment.query.join(Incident).filter(
            IncidentAssignment.department == department,
            IncidentAssignment.active.is_(True),
            Incident.status.notin_(["Resolved"]),
        ).count()
    else:
        recent_cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_incident_ids = {
            item.incident_id for item in audits
            if item.incident_id is not None and item.created_at and item.created_at >= recent_cutoff
        }
        if recent_incident_ids:
            active_case_count = Incident.query.filter(
                Incident.id.in_(list(recent_incident_ids)),
                Incident.status != "Resolved",
            ).count()
        else:
            active_case_count = 0

    if active_case_count <= 3:
        workload_indicator = "Low"
    elif active_case_count <= 7:
        workload_indicator = "Moderate"
    else:
        workload_indicator = "High"

    session_start = getattr(user, "current_session_started_at", None)
    session_seconds = 0
    if session_start:
        session_seconds = max(0, int((datetime.utcnow() - session_start).total_seconds()))

    return {
        "cases_reviewed": len(reviewed_ids),
        "cases_dispatched": len(dispatched_ids),
        "cases_handled": len(handled_ids),
        "average_review_seconds": (
            round(sum(review_seconds) / len(review_seconds), 1)
            if review_seconds else None
        ),
        "active_case_count": active_case_count,
        "workload_indicator": workload_indicator,
        "current_session_seconds": session_seconds,
    }


def _boolean_value(data, key, current):
    if key not in data:
        return current
    value = data.get(key)
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

def _current_role():
    return str(getattr(current_user, "role", "") or "").strip().lower()


def _requested_view_department():
    """Return the safe department view requested for this GET request.

    Department accounts are permanently scoped to their own department.
    Admin and dispatcher accounts may narrow the response for demonstrations
    without changing authentication or gaining any additional permission.
    """
    role = _current_role()
    own_department = ROLE_DEPARTMENT.get(role)
    if own_department:
        return own_department
    if role not in {"admin", "dispatcher"}:
        return None
    requested_role = str(request.args.get("view_role", "") or "").strip().lower()
    return ROLE_DEPARTMENT.get(requested_role)


def _facility_query_for_current_user():
    query = Facility.query.filter(Facility.active.is_(True))
    required_department = _requested_view_department()
    if required_department:
        query = query.filter(Facility.department == required_department)
    return query


def _visible_departments():
    role = _current_role()
    requested_department = _requested_view_department()
    if requested_department:
        return [requested_department]
    if role in {"admin", "dispatcher"}:
        return sorted(ALLOWED_DEPARTMENTS)
    department = ROLE_DEPARTMENT.get(role)
    return [department] if department else []


def _can_view_department(department):
    return str(department or "").strip().upper() in _visible_departments()


def _can_manage_department_resources(department):
    department = str(department or "").strip().upper()
    role = _current_role()
    if role in {"admin", "dispatcher"}:
        return department in ALLOWED_DEPARTMENTS
    return ROLE_DEPARTMENT.get(role) == department


def _resource_query_for_current_user():
    query = DepartmentResource.query.filter(DepartmentResource.active.is_(True))
    visible = _visible_departments()
    if not visible:
        return query.filter(DepartmentResource.id == -1)
    if len(visible) == 1:
        query = query.filter(DepartmentResource.department == visible[0])
    return query


def _department_overview(department):
    department = str(department or "").strip().upper()
    facilities = Facility.query.filter(
        Facility.active.is_(True),
        Facility.department == department,
    ).order_by(Facility.name.asc()).all()
    resources = DepartmentResource.query.filter(
        DepartmentResource.active.is_(True),
        DepartmentResource.department == department,
    ).order_by(DepartmentResource.resource_type.asc(), DepartmentResource.name.asc()).all()

    active_assignments = IncidentAssignment.query.options(
        selectinload(IncidentAssignment.incident)
    ).filter(
        IncidentAssignment.department == department,
        IncidentAssignment.active.is_(True),
    ).all()
    assigned_incidents = {
        assignment.incident_id: assignment.incident
        for assignment in active_assignments
        if assignment.incident is not None
    }
    active_incidents = [
        incident for incident in assigned_incidents.values()
        if str(incident.status or "").strip().upper() != "RESOLVED"
    ]
    dispatched_incidents = [
        incident for incident in active_incidents
        if str(incident.status or "").strip().upper() in {"DISPATCHED", "ESCALATED"}
    ]

    historical_ids = {
        incident_id for (incident_id,) in db.session.query(IncidentAssignment.incident_id)
        .filter(IncidentAssignment.department == department).all()
    }
    historical_incidents = (
        Incident.query.filter(Incident.id.in_(historical_ids)).all()
        if historical_ids else []
    )
    response_minutes = [
        (incident.dispatched_at - incident.created_at).total_seconds() / 60
        for incident in historical_incidents
        if incident.created_at and incident.dispatched_at
        and incident.dispatched_at >= incident.created_at
    ]

    available_personnel = sum(
        1 for item in resources
        if item.resource_type == "PERSONNEL" and item.status == "AVAILABLE"
    )
    total_personnel = sum(1 for item in resources if item.resource_type == "PERSONNEL")
    available_vehicles = sum(
        1 for item in resources
        if item.resource_type == "VEHICLE" and item.status == "AVAILABLE"
    )
    total_vehicles = sum(1 for item in resources if item.resource_type == "VEHICLE")
    unavailable_resources = sum(
        1 for item in resources
        if item.status in {"UNAVAILABLE", "MAINTENANCE"}
    )

    update_candidates = []
    update_candidates.extend(item.updated_at for item in resources if item.updated_at)
    update_candidates.extend(item.updated_at for item in facilities if item.updated_at)
    update_candidates.extend(item.updated_at for item in active_incidents if item.updated_at)
    update_candidates.extend(item.assigned_at for item in active_assignments if item.assigned_at)
    last_update = max(update_candidates) if update_candidates else None

    labels = {
        "POLICE": "Police",
        "FIRE": "Fire & Rescue",
        "MEDICAL": "Medical",
    }
    coverage_areas = sorted({
        str(item.coverage_area).strip()
        for item in facilities
        if str(item.coverage_area or "").strip()
    })

    return {
        "department": department,
        "display_name": labels.get(department, department.title()),
        "active_incidents": len(active_incidents),
        "dispatched_incidents": len(dispatched_incidents),
        "available_personnel": available_personnel,
        "total_personnel": total_personnel,
        "available_vehicles": available_vehicles,
        "total_vehicles": total_vehicles,
        "unavailable_resources": unavailable_resources,
        "average_response_minutes": (
            round(sum(response_minutes) / len(response_minutes), 1)
            if response_minutes else None
        ),
        "last_status_update": last_update.isoformat() if last_update else None,
        "coverage_areas": coverage_areas,
        "facility_count": len(facilities),
        "facilities": [item.to_dict() for item in facilities],
        "resources": [item.to_dict() for item in resources],
        "can_manage_resources": _can_manage_department_resources(department),
    }


def _can_manage_incidents():
    return str(getattr(current_user, "role", "") or "").lower() in {
        "admin",
        "dispatcher",
    }


def _normalise_departments(value):
    if not isinstance(value, list):
        return []

    departments = []
    for item in value:
        department = str(item or "").strip().upper()
        if department in ALLOWED_DEPARTMENTS and department not in departments:
            departments.append(department)
    return departments


def _active_department_names(incident):
    return [
        assignment.department
        for assignment in incident.assignments
        if assignment.active
    ]


def _sync_assignments(incident, requested_departments, actor_id):
    """Replace the active department set while preserving assignment history."""
    requested = set(_normalise_departments(requested_departments))
    now = datetime.utcnow()

    active_by_department = {
        assignment.department: assignment
        for assignment in incident.assignments
        if assignment.active
    }

    for department, assignment in active_by_department.items():
        if department not in requested:
            assignment.active = False
            assignment.removed_at = now
            assignment.removed_by_id = actor_id

    for department in sorted(requested):
        if department not in active_by_department:
            incident.assignments.append(
                IncidentAssignment(
                    department=department,
                    active=True,
                    assigned_at=now,
                    assigned_by_id=actor_id,
                )
            )

    active_names = sorted(requested)
    incident.dispatch_agency = (
        ", ".join(name.title() for name in active_names)
        if active_names
        else None
    )
    return active_names


def _serialize_incident(incident):
    data = incident.to_dict()
    if not getattr(current_user, "is_authenticated", False) or not _can_manage_incidents():
        data.pop("assignment_records", None)
    return data


def _send_dispatch_sms(incident):
    if not incident.phone_number:
        return False, "No phone number is available for this incident."

    try:
        response = send_help_is_coming_sms(
            phone_number=incident.phone_number,
            incident_id=incident.id,
        )
        print(f"SMS sent successfully: {response}")
        return True, None
    except Exception as error:
        print(f"Dispatch confirmation SMS failed: {error}")
        return False, str(error)


def _haversine_km(lat1, lon1, lat2, lon2):
    earth_radius_km = 6371.0088
    phi1, phi2 = radians(lat1), radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)

    value = (
        sin(delta_phi / 2) ** 2
        + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
    )
    return 2 * earth_radius_km * atan2(sqrt(value), sqrt(1 - value))


def _incident_query():
    return Incident.query.options(selectinload(Incident.assignments))


def _department_user_can_view(incident):
    role = _current_role()
    required_department = _requested_view_department()
    if role in {"admin", "dispatcher"} and not required_department:
        return True
    return bool(
        required_department
        and required_department in _active_department_names(incident)
    )



def _operational_upload_folder():
    folder = current_app.config.get("OPERATIONAL_REPORT_UPLOAD_FOLDER")
    if not folder:
        folder = os.path.join(
            current_app.instance_path,
            "uploads",
            "operational_reports",
        )
    os.makedirs(folder, exist_ok=True)
    return folder


def _parse_completed_at(value):
    value = str(value or "").strip()
    if not value:
        return datetime.utcnow()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed


def _operational_report_visible(report):
    incident = getattr(report, "incident", None)
    if incident is None or not _department_user_can_view(incident):
        return False

    role = _current_role()
    if role in {"admin", "dispatcher"}:
        view_department = _requested_view_department()
        return not view_department or report.department == view_department

    return report.department == ROLE_DEPARTMENT.get(role)


def _can_manage_operational_report(report):
    role = _current_role()
    if role in {"admin", "dispatcher"}:
        return True
    return (
        report.department == ROLE_DEPARTMENT.get(role)
        and _department_user_can_view(report.incident)
    )


def _operational_report_query():
    return OperationalReport.query.options(
        selectinload(OperationalReport.incident).selectinload(Incident.assignments),
        selectinload(OperationalReport.attachments),
    )


def _validate_operational_report_payload(data, incident, *, existing=None):
    role = _current_role()
    department = str(data.get("department", getattr(existing, "department", "")) or "").strip().upper()
    if department not in ALLOWED_DEPARTMENTS:
        return None, "Select Police, Fire or Medical as the reporting department."

    own_department = ROLE_DEPARTMENT.get(role)
    if own_department and department != own_department:
        return None, "You can only submit a report for your own department."

    active_departments = sorted(_active_department_names(incident))
    if department not in active_departments:
        return None, "The reporting department must be assigned to this incident."

    responder_name = str(data.get("responder_name", "") or "").strip()
    findings = str(data.get("findings", "") or "").strip()
    actions_taken = str(data.get("actions_taken", "") or "").strip()
    outcome = str(data.get("outcome", "") or "").strip()
    resources_used = str(data.get("resources_used", "") or "").strip() or None
    final_classification = str(
        data.get("final_classification", incident.incident_type or "") or ""
    ).strip().upper()
    final_departments = _normalise_departments(
        data.get("final_departments", active_departments)
    )
    completed_at = _parse_completed_at(data.get("completed_at"))

    try:
        people_affected = int(data.get("people_affected", 0) or 0)
    except (TypeError, ValueError):
        return None, "People affected must be a whole number."

    if not responder_name:
        return None, "Responder or officer name is required."
    if not findings:
        return None, "Describe what responders found."
    if not actions_taken:
        return None, "Describe the actions taken."
    if not outcome:
        return None, "Describe the incident outcome."
    if people_affected < 0:
        return None, "People affected cannot be negative."
    if final_classification not in ALLOWED_TYPES:
        return None, "Final classification must be MEDICAL, FIRE or CRIME."
    if not final_departments:
        return None, "Select at least one final department assignment."
    if completed_at is None:
        return None, "The completion date is invalid."

    return {
        "department": department,
        "responder_name": responder_name[:160],
        "findings": findings,
        "actions_taken": actions_taken,
        "outcome": outcome,
        "people_affected": people_affected,
        "resources_used": resources_used,
        "final_classification": final_classification,
        "final_departments": final_departments,
        "completed_at": completed_at,
    }, None


@main.route("/")
def home():
    return redirect(url_for("main.login"))


@main.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        from app.models.user import User

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            now = datetime.utcnow()
            user.last_login_at = now
            user.current_session_started_at = now
            user.updated_at = now
            db.session.commit()
            login_user(user)
            return redirect(url_for("main.dashboard"))

        return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")


@main.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.login"))


@main.route("/dashboard")
@login_required
def dashboard():
    return render_template(
        "dashboard.html",
        user_role=current_user.role,
        current_username=getattr(current_user, "username", "Operator"),
        current_display_name=getattr(current_user, "display_name", None) or getattr(current_user, "username", "Operator"),
    )



@main.route("/api/settings", methods=["GET"])
@login_required
def get_settings():
    preferences = _user_preferences(current_user)
    profile = current_user.to_profile_dict()
    role = str(profile.get("role") or "").strip().lower()
    if not profile.get("department"):
        profile["department"] = ROLE_DEPARTMENT.get(role) or "OPERATIONS"
    profile["profile_image_url"] = (
        url_for("main.profile_image", v=int(current_user.updated_at.timestamp()) if current_user.updated_at else 0)
        if current_user.profile_image_filename else None
    )

    payload = {
        "profile": profile,
        "metrics": _profile_metrics(current_user),
        "preferences": preferences.to_dict(),
        "system": None,
        "can_manage_system": _current_role() == "admin",
    }
    if payload["can_manage_system"]:
        payload["system"] = _system_settings().to_dict()
    return jsonify(payload)


@main.route("/api/account/profile", methods=["PATCH"])
@login_required
def update_account_profile():
    data = request.get_json(silent=True) or {}
    full_name = str(data.get("full_name", "") or "").strip()
    phone_number = str(data.get("phone_number", "") or "").strip()

    if len(full_name) > 120:
        return jsonify({"message": "Name must be 120 characters or fewer."}), 400
    if len(phone_number) > 30:
        return jsonify({"message": "Phone number must be 30 characters or fewer."}), 400

    current_user.full_name = full_name or None
    current_user.phone_number = phone_number or None
    current_user.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({
        "message": "Profile saved.",
        "profile": current_user.to_profile_dict(),
    })


@main.route("/api/account/profile-image", methods=["GET"])
@login_required
def profile_image():
    filename = str(getattr(current_user, "profile_image_filename", "") or "").strip()
    if not filename:
        return jsonify({"message": "No profile image is stored."}), 404
    return send_from_directory(_profile_image_directory(), filename, as_attachment=False)


@main.route("/api/account/profile-image", methods=["POST"])
@login_required
def upload_profile_image():
    storage = request.files.get("profile_image")
    if storage is None or not storage.filename:
        return jsonify({"message": "Select an image file."}), 400

    original_name = secure_filename(storage.filename)
    extension = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if extension not in ALLOWED_PROFILE_IMAGE_EXTENSIONS:
        return jsonify({"message": "Use PNG, JPG, JPEG or WEBP."}), 400
    if not str(storage.mimetype or "").lower().startswith("image/"):
        return jsonify({"message": "The selected file is not a valid image."}), 400

    content = storage.read(MAX_PROFILE_IMAGE_BYTES + 1)
    if not content:
        return jsonify({"message": "The selected image is empty."}), 400
    if len(content) > MAX_PROFILE_IMAGE_BYTES:
        return jsonify({"message": "Profile images must be 5 MB or smaller."}), 400

    directory = _profile_image_directory()
    new_filename = f"user-{current_user.id}-{uuid4().hex}.{extension}"
    new_path = os.path.join(directory, new_filename)
    with open(new_path, "wb") as output_file:
        output_file.write(content)

    previous_filename = str(current_user.profile_image_filename or "").strip()
    current_user.profile_image_filename = new_filename
    current_user.updated_at = datetime.utcnow()
    db.session.commit()

    if previous_filename and previous_filename != new_filename:
        previous_path = os.path.join(directory, previous_filename)
        try:
            if os.path.isfile(previous_path):
                os.remove(previous_path)
        except OSError:
            current_app.logger.warning("Could not remove old profile image %s", previous_path)

    return jsonify({
        "message": "Profile image updated.",
        "profile_image_url": url_for("main.profile_image", v=int(current_user.updated_at.timestamp())),
    })


@main.route("/api/account/password", methods=["POST"])
@login_required
def change_account_password():
    data = request.get_json(silent=True) or {}
    current_password = str(data.get("current_password", "") or "")
    new_password = str(data.get("new_password", "") or "")
    confirm_password = str(data.get("confirm_password", "") or "")

    if not current_user.check_password(current_password):
        return jsonify({"message": "Current password is incorrect."}), 400
    if len(new_password) < 8:
        return jsonify({"message": "New password must contain at least 8 characters."}), 400
    if new_password != confirm_password:
        return jsonify({"message": "New password and confirmation do not match."}), 400
    if current_user.check_password(new_password):
        return jsonify({"message": "Choose a password different from the current password."}), 400

    current_user.set_password(new_password)
    current_user.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"message": "Password changed successfully."})


@main.route("/api/account/preferences", methods=["PATCH"])
@login_required
def update_account_preferences():
    data = request.get_json(silent=True) or {}
    preference = _user_preferences(current_user)

    theme = str(data.get("theme", preference.theme) or "").strip().lower()
    language = str(data.get("language", preference.language) or "").strip().lower()
    try:
        refresh_seconds = int(data.get("auto_refresh_seconds", preference.auto_refresh_seconds))
    except (TypeError, ValueError):
        return jsonify({"message": "Auto-refresh interval is invalid."}), 400

    if theme not in ALLOWED_THEMES:
        return jsonify({"message": "Theme must be dark, light or system."}), 400
    if language not in ALLOWED_LANGUAGES:
        return jsonify({"message": "Language must be English or Nyanja."}), 400
    if refresh_seconds not in ALLOWED_REFRESH_SECONDS:
        return jsonify({"message": "Auto-refresh interval is not supported."}), 400

    preference.theme = theme
    preference.language = language
    preference.auto_refresh_seconds = refresh_seconds
    preference.critical_sound_enabled = _boolean_value(data, "critical_sound_enabled", preference.critical_sound_enabled)
    preference.desktop_notifications_enabled = _boolean_value(data, "desktop_notifications_enabled", preference.desktop_notifications_enabled)
    preference.map_show_incidents = _boolean_value(data, "map_show_incidents", preference.map_show_incidents)
    preference.map_show_facilities = _boolean_value(data, "map_show_facilities", preference.map_show_facilities)
    preference.map_show_heat = _boolean_value(data, "map_show_heat", preference.map_show_heat)
    preference.map_cluster_incidents = _boolean_value(data, "map_cluster_incidents", preference.map_cluster_incidents)
    preference.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"message": "Preferences saved.", "preferences": preference.to_dict()})


@main.route("/api/system-settings", methods=["PATCH"])
@login_required
def update_system_settings():
    if _current_role() != "admin":
        return jsonify({"message": "Administrator access is required."}), 403

    data = request.get_json(silent=True) or {}
    settings = _system_settings()
    try:
        threshold = float(data.get("nlp_confidence_threshold", settings.nlp_confidence_threshold))
        refresh_seconds = int(data.get("default_refresh_seconds", settings.default_refresh_seconds))
    except (TypeError, ValueError):
        return jsonify({"message": "System setting values are invalid."}), 400
    language = str(data.get("default_language", settings.default_language) or "").strip().lower()

    if threshold < 0.50 or threshold > 0.95:
        return jsonify({"message": "NLP threshold must be between 50% and 95%."}), 400
    if refresh_seconds not in ALLOWED_REFRESH_SECONDS:
        return jsonify({"message": "Default refresh interval is not supported."}), 400
    if language not in ALLOWED_LANGUAGES:
        return jsonify({"message": "Default language must be English or Nyanja."}), 400

    settings.nlp_confidence_threshold = round(threshold, 2)
    settings.default_refresh_seconds = refresh_seconds
    settings.default_language = language
    settings.updated_by_id = current_user.id
    settings.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"message": "System configuration saved.", "system": settings.to_dict()})


@main.route("/report-page")
def report_page():
    return render_template("report.html")


@main.route("/report", methods=["POST"])
def report():
    from app.nlp.triage import triage

    data = request.get_json(silent=True) if request.is_json else request.form
    data = data or {}

    raw_text = str(data.get("raw_text", "")).strip()
    phone = str(data.get("phone_number", "")).strip() or None
    readable_location = str(data.get("location", "")).strip()[:255] or None
    channel = (str(data.get("channel", "WEB")).strip().upper() or "WEB")[:10]
    default_language = str(_system_settings().default_language or "en").strip().lower()
    language = (str(data.get("language", default_language)).strip().lower() or default_language)[:5]
    latitude = data.get("latitude")
    longitude = data.get("longitude")

    if not raw_text:
        return jsonify({
            "success": False,
            "message": "Emergency description is required.",
        }), 400

    try:
        latitude = float(latitude) if latitude not in (None, "") else None
        longitude = float(longitude) if longitude not in (None, "") else None
    except (TypeError, ValueError):
        return jsonify({
            "success": False,
            "message": "Invalid location coordinates.",
        }), 400

    if latitude is not None and not -90 <= latitude <= 90:
        return jsonify({"success": False, "message": "Invalid latitude."}), 400
    if longitude is not None and not -180 <= longitude <= 180:
        return jsonify({"success": False, "message": "Invalid longitude."}), 400

    triage_result = triage(raw_text)
    incident_type = str(triage_result.get("incident_type", "")).strip().upper()
    severity = str(triage_result.get("severity", "LOW")).strip().upper()
    confidence = float(triage_result.get("confidence", 0.0) or 0.0)
    if confidence > 1:
        confidence = confidence / 100
    confidence = max(0.0, min(confidence, 1.0))

    if incident_type not in ALLOWED_TYPES:
        incident_type = None
    if severity not in ALLOWED_SEVERITIES:
        severity = "LOW"

    classification_status = (
        "AI Classified"
        if incident_type and confidence >= _nlp_confidence_threshold()
        else "Needs Review"
    )

    incident = Incident(
        raw_text=raw_text,
        channel=channel,
        incident_type=incident_type,
        severity=severity,
        location=readable_location,
        latitude=latitude,
        longitude=longitude,
        phone_number=phone,
        language=language,
        status="Pending",
        dispatcher_notes=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        nlp_confidence=confidence,
        classification_status=classification_status,
    )

    db.session.add(incident)
    db.session.flush()
    initial_departments = _default_departments_for_incident_type(incident_type)
    if initial_departments:
        _sync_assignments(incident, initial_departments, actor_id=None)
    audit = _create_audit(
        incident,
        "INCIDENT_REPORTED",
        previous_status=None,
        new_status="Pending",
        previous_departments=[],
        new_departments=initial_departments,
        notes=raw_text,
        details={
            "readable_location": readable_location,
            "latitude": latitude,
            "longitude": longitude,
            "language": language,
            "ai_classification": incident_type,
            "severity": severity,
            "confidence": confidence,
            "classification_status": classification_status,
            "initial_departments": initial_departments,
        },
        actor=None,
    )
    db.session.commit()

    incident_data = _serialize_incident(incident)
    socketio.emit("incident_feed_changed", {"incident_id": incident.id, "change": "created"})
    _emit_audit(audit)

    return jsonify({
        "success": True,
        "message": "Emergency report received successfully.",
        "ref_id": incident_data["reference_id"],
        "data": incident_data,
    }), 201


@main.route("/api/incidents", methods=["GET"])
@login_required
def get_incidents():
    incidents = _incident_query().order_by(Incident.created_at.desc()).all()
    visible = [incident for incident in incidents if _department_user_can_view(incident)]
    return jsonify([_serialize_incident(incident) for incident in visible])


@main.route("/api/incidents/<int:incident_id>", methods=["GET"])
@login_required
def get_incident(incident_id):
    incident = _incident_query().filter_by(id=incident_id).first_or_404()
    if not _department_user_can_view(incident):
        return jsonify({"message": "You are not assigned to this incident."}), 403
    return jsonify(_serialize_incident(incident))


@main.route("/api/facilities", methods=["GET"])
@login_required
def get_facilities():
    _ensure_default_facilities()
    department = str(request.args.get("department", "") or "").strip().upper()
    if department and department not in ALLOWED_DEPARTMENTS:
        return jsonify({"message": "Invalid department filter."}), 400

    query = _facility_query_for_current_user()
    if department:
        query = query.filter(Facility.department == department)

    facilities = query.order_by(Facility.department.asc(), Facility.name.asc()).all()
    return jsonify([facility.to_dict() for facility in facilities])


@main.route("/api/facilities/nearby", methods=["GET"])
@login_required
def nearby_facilities():
    try:
        latitude = float(request.args.get("latitude", ""))
        longitude = float(request.args.get("longitude", ""))
    except (TypeError, ValueError):
        return jsonify({"message": "Valid latitude and longitude are required."}), 400

    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return jsonify({"message": "Coordinates are outside the valid range."}), 400

    _ensure_default_facilities()
    facilities = _facility_query_for_current_user().all()
    results = []
    for facility in facilities:
        item = facility.to_dict()
        item["distance_km"] = round(
            _haversine_km(
                latitude,
                longitude,
                facility.latitude,
                facility.longitude,
            ),
            2,
        )
        results.append(item)

    results.sort(key=lambda item: item["distance_km"])
    return jsonify(results)


@main.route("/api/departments/overview", methods=["GET"])
@login_required
def get_department_overview():
    departments = _visible_departments()
    if not departments:
        return jsonify({"message": "Your account does not have department access."}), 403

    _ensure_default_facilities()
    _ensure_demo_department_resources()
    view_department = _requested_view_department()
    return jsonify({
        "role": _current_role(),
        "view_department": view_department,
        "demo_resources_seeded": True,
        "departments": [_department_overview(item) for item in departments],
    })


@main.route("/api/departments/<department>/resources", methods=["GET"])
@login_required
def get_department_resources(department):
    department = str(department or "").strip().upper()
    if department not in ALLOWED_DEPARTMENTS:
        return jsonify({"message": "Invalid department."}), 400
    if not _can_view_department(department):
        return jsonify({"message": "You cannot view another department's resources."}), 403

    return jsonify(_department_overview(department))


@main.route("/api/department-resources", methods=["POST"])
@login_required
def create_department_resource():
    data = request.get_json(silent=True) or {}
    department = str(data.get("department", "") or "").strip().upper()
    resource_type = str(data.get("resource_type", "") or "").strip().upper()
    status = str(data.get("status", "AVAILABLE") or "AVAILABLE").strip().upper()
    name = str(data.get("name", "") or "").strip()
    identifier = str(data.get("identifier", "") or "").strip() or None
    details = str(data.get("details", "") or "").strip() or None

    if department not in ALLOWED_DEPARTMENTS:
        return jsonify({"message": "Invalid department."}), 400
    if not _can_manage_department_resources(department):
        return jsonify({"message": "You cannot manage another department's resources."}), 403
    if resource_type not in RESOURCE_TYPES:
        return jsonify({"message": "Resource type must be PERSONNEL, VEHICLE or EQUIPMENT."}), 400
    if status not in RESOURCE_STATUSES:
        return jsonify({"message": "Invalid resource status."}), 400
    if not name:
        return jsonify({"message": "Resource name is required."}), 400

    facility_id = data.get("facility_id")
    facility = None
    if facility_id not in (None, ""):
        try:
            facility_id = int(facility_id)
        except (TypeError, ValueError):
            return jsonify({"message": "Invalid facility."}), 400
        facility = Facility.query.filter_by(id=facility_id, department=department, active=True).first()
        if not facility:
            return jsonify({"message": "The selected facility does not belong to this department."}), 400

    resource = DepartmentResource(
        department=department,
        resource_type=resource_type,
        name=name[:160],
        identifier=identifier[:80] if identifier else None,
        status=status,
        details=details,
        active=True,
        facility_id=facility.id if facility else None,
        updated_by_id=current_user.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.session.add(resource)
    db.session.commit()
    socketio.emit("department_data_changed", {"change": "resource-created"})
    return jsonify({"message": "resource created", "data": resource.to_dict()}), 201


@main.route("/api/department-resources/<int:resource_id>", methods=["PATCH"])
@login_required
def update_department_resource(resource_id):
    resource = DepartmentResource.query.filter_by(id=resource_id, active=True).first_or_404()
    if not _can_manage_department_resources(resource.department):
        return jsonify({"message": "You cannot manage another department's resources."}), 403

    data = request.get_json(silent=True) or {}
    if "status" in data:
        status = str(data.get("status", "") or "").strip().upper()
        if status not in RESOURCE_STATUSES:
            return jsonify({"message": "Invalid resource status."}), 400
        resource.status = status
    if "name" in data:
        name = str(data.get("name", "") or "").strip()
        if not name:
            return jsonify({"message": "Resource name cannot be empty."}), 400
        resource.name = name[:160]
    if "identifier" in data:
        identifier = str(data.get("identifier", "") or "").strip()
        resource.identifier = identifier[:80] if identifier else None
    if "details" in data:
        resource.details = str(data.get("details", "") or "").strip() or None
    if "facility_id" in data:
        facility_id = data.get("facility_id")
        if facility_id in (None, ""):
            resource.facility_id = None
        else:
            try:
                facility_id = int(facility_id)
            except (TypeError, ValueError):
                return jsonify({"message": "Invalid facility."}), 400
            facility = Facility.query.filter_by(
                id=facility_id,
                department=resource.department,
                active=True,
            ).first()
            if not facility:
                return jsonify({"message": "The selected facility does not belong to this department."}), 400
            resource.facility_id = facility.id

    resource.updated_by_id = current_user.id
    resource.updated_at = datetime.utcnow()
    db.session.commit()
    socketio.emit("department_data_changed", {"change": "resource-updated"})
    return jsonify({"message": "resource updated", "data": resource.to_dict()})



def _percentage(part, whole):
    return round((part / whole) * 100, 1) if whole else 0.0


def _count_values(items, getter, preferred_order=None):
    counts = {}
    for item in items:
        value = str(getter(item) or "UNKNOWN").strip().upper() or "UNKNOWN"
        counts[value] = counts.get(value, 0) + 1
    if preferred_order:
        ordered = {key: counts.pop(key, 0) for key in preferred_order}
        ordered.update(dict(sorted(counts.items())))
        return ordered
    return dict(sorted(counts.items()))


@main.route("/api/analytics", methods=["GET"])
@login_required
def get_analytics():
    incidents = _incident_query().order_by(Incident.created_at.asc()).all()
    incidents = [incident for incident in incidents if _department_user_can_view(incident)]
    total = len(incidents)

    statuses = _count_values(
        incidents,
        lambda item: item.status,
        ["PENDING", "DISPATCHED", "ESCALATED", "RESOLVED"],
    )
    types = _count_values(incidents, lambda item: item.incident_type, ["MEDICAL", "CRIME", "FIRE"])
    severities = _count_values(incidents, lambda item: item.severity, ["CRITICAL", "HIGH", "LOW"])
    channels = _count_values(incidents, lambda item: item.channel, ["WEB", "USSD", "SMS"])

    response_minutes = [
        (incident.dispatched_at - incident.created_at).total_seconds() / 60
        for incident in incidents
        if incident.created_at and incident.dispatched_at
        and incident.dispatched_at >= incident.created_at
    ]
    resolution_minutes = [
        (incident.resolved_at - incident.created_at).total_seconds() / 60
        for incident in incidents
        if incident.created_at and incident.resolved_at
        and incident.resolved_at >= incident.created_at
    ]

    now_local = datetime.utcnow() + timedelta(hours=2)
    day_keys = [
        (now_local - timedelta(days=offset)).strftime("%Y-%m-%d")
        for offset in range(6, -1, -1)
    ]
    reports_by_day = {key: 0 for key in day_keys}
    reports_by_hour = {str(hour).zfill(2): 0 for hour in range(24)}
    for incident in incidents:
        if not incident.created_at:
            continue
        local_created = incident.created_at + timedelta(hours=2)
        day_key = local_created.strftime("%Y-%m-%d")
        if day_key in reports_by_day:
            reports_by_day[day_key] += 1
        reports_by_hour[local_created.strftime("%H")] += 1

    visible_ids = {incident.id for incident in incidents}
    audits = []
    if visible_ids:
        audits = IncidentAudit.query.filter(IncidentAudit.incident_id.in_(visible_ids)).all()
        audits = [record for record in audits if _audit_visible_to_current_user(record)]

    dispatcher_workload = {}
    for record in audits:
        if record.action not in {
            "NOTE_ADDED", "NOTE_UPDATED", "CLASSIFICATION_CORRECTED",
            "CLASSIFICATION_CONFIRMED", "ASSIGNMENT_UPDATED", "DISPATCHED",
            "ESCALATED", "RESOLVED", "STATUS_UPDATED",
        }:
            continue
        username = str(record.actor_username or "System").strip() or "System"
        dispatcher_workload[username] = dispatcher_workload.get(username, 0) + 1

    corrections = sum(1 for record in audits if record.action == "CLASSIFICATION_CORRECTED")
    escalations = sum(1 for record in audits if record.action == "ESCALATED")

    department_workload = {}
    departments = _visible_departments()
    for department in departments:
        assignments = IncidentAssignment.query.filter(
            IncidentAssignment.department == department,
            IncidentAssignment.active.is_(True),
        ).all()
        active = 0
        dispatched = 0
        for assignment in assignments:
            incident = assignment.incident
            if incident is None or incident.id not in visible_ids:
                continue
            status = str(incident.status or "").strip().upper()
            if status != "RESOLVED":
                active += 1
            if status in {"DISPATCHED", "ESCALATED"}:
                dispatched += 1
        department_workload[department] = {
            "active": active,
            "dispatched": dispatched,
        }

    hotspots = {}
    for incident in incidents:
        location = str(incident.location or "Unknown location").strip() or "Unknown location"
        key = location.split(",")[0].strip() or location
        hotspots[key] = hotspots.get(key, 0) + 1

    confidence_values = [
        float(incident.nlp_confidence)
        for incident in incidents
        if incident.nlp_confidence is not None
    ]
    below_threshold = sum(1 for value in confidence_values if value < _nlp_confidence_threshold())
    resolved = statuses.get("RESOLVED", 0)

    return jsonify({
        "scope": {
            "authenticated_role": _current_role(),
            "view_department": _requested_view_department(),
        },
        "summary": {
            "total": total,
            "pending": statuses.get("PENDING", 0),
            "dispatched": statuses.get("DISPATCHED", 0) + statuses.get("ESCALATED", 0),
            "resolved": resolved,
            "resolution_rate": _percentage(resolved, total),
            "average_response_minutes": round(sum(response_minutes) / len(response_minutes), 1) if response_minutes else None,
            "average_resolution_minutes": round(sum(resolution_minutes) / len(resolution_minutes), 1) if resolution_minutes else None,
        },
        "incidents_by_type": types,
        "incidents_by_severity": severities,
        "incidents_by_channel": channels,
        "response_status": statuses,
        "reports_by_day": [{"date": key, "count": reports_by_day[key]} for key in day_keys],
        "reports_by_hour": [{"hour": key, "count": reports_by_hour[key]} for key in reports_by_hour],
        "dispatcher_workload": [
            {"name": name, "actions": count}
            for name, count in sorted(dispatcher_workload.items(), key=lambda item: (-item[1], item[0]))[:10]
        ],
        "department_workload": department_workload,
        "location_hotspots": [
            {"location": name, "count": count}
            for name, count in sorted(hotspots.items(), key=lambda item: (-item[1], item[0]))[:10]
        ],
        "classification": {
            "average_confidence": round(sum(confidence_values) / len(confidence_values), 3) if confidence_values else None,
            "below_threshold": below_threshold,
            "threshold": _nlp_confidence_threshold(),
            "corrections": corrections,
            "correction_rate": _percentage(corrections, total),
            "escalations": escalations,
            "escalation_rate": _percentage(escalations, total),
        },
    })



@main.route("/api/operational-reports", methods=["GET"])
@login_required
def get_operational_reports():
    reports = _operational_report_query().order_by(
        OperationalReport.completed_at.desc(),
        OperationalReport.id.desc(),
    ).all()
    reports = [report for report in reports if _operational_report_visible(report)]

    search = str(request.args.get("search", "") or "").strip().lower()
    if search:
        reports = [
            report for report in reports
            if search in " ".join([
                f"RESQ-{report.incident_id:04d}",
                str(report.department or ""),
                str(report.responder_name or ""),
                str(report.findings or ""),
                str(report.actions_taken or ""),
                str(report.outcome or ""),
                str(report.final_classification or ""),
                " ".join(report.final_departments or []),
            ]).lower()
        ]

    return jsonify({
        "items": [report.to_dict() for report in reports],
        "total": len(reports),
    })


@main.route("/api/incidents/<int:incident_id>/operational-reports", methods=["GET", "POST"])
@login_required
def incident_operational_reports(incident_id):
    incident = _incident_query().filter_by(id=incident_id).first_or_404()
    if not _department_user_can_view(incident):
        return jsonify({"message": "You are not assigned to this incident."}), 403

    if request.method == "GET":
        reports = _operational_report_query().filter_by(incident_id=incident.id).order_by(
            OperationalReport.completed_at.desc()
        ).all()
        reports = [report for report in reports if _operational_report_visible(report)]
        return jsonify({
            "items": [report.to_dict() for report in reports],
            "eligible": normalise_status_for_report(incident.status),
            "active_departments": sorted(_active_department_names(incident)),
        })

    if str(incident.status or "").strip().upper() not in OPERATIONAL_REPORT_STATUSES:
        return jsonify({
            "message": "An operational report can only be added after dispatch, escalation or resolution."
        }), 409

    data = request.get_json(silent=True) or {}
    values, error = _validate_operational_report_payload(data, incident)
    if error:
        return jsonify({"message": error}), 400

    existing = OperationalReport.query.filter_by(
        incident_id=incident.id,
        department=values["department"],
    ).first()
    if existing:
        return jsonify({
            "message": "This department already has an operational report for the incident.",
            "report_id": existing.id,
        }), 409

    report = OperationalReport(
        incident_id=incident.id,
        created_by_id=current_user.id,
        updated_by_id=current_user.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        **values,
    )
    db.session.add(report)
    audit = _create_audit(
        incident,
        "OPERATIONAL_REPORT_SAVED",
        previous_status=incident.status,
        new_status=incident.status,
        previous_departments=_active_department_names(incident),
        new_departments=values["final_departments"],
        notes=values["outcome"],
        details={
            "report_department": values["department"],
            "responder_name": values["responder_name"],
            "people_affected": values["people_affected"],
            "final_classification": values["final_classification"],
            "report_action": "created",
        },
    )
    db.session.commit()
    socketio.emit("operational_report_changed", {
        "incident_id": incident.id,
        "report_id": report.id,
        "change": "created",
    })
    _emit_audit(audit)
    return jsonify({"message": "operational report saved", "data": report.to_dict()}), 201


def normalise_status_for_report(value):
    return str(value or "").strip().upper() in OPERATIONAL_REPORT_STATUSES


@main.route("/api/operational-reports/<int:report_id>", methods=["GET", "PATCH"])
@login_required
def operational_report_detail(report_id):
    report = _operational_report_query().filter_by(id=report_id).first_or_404()
    if not _operational_report_visible(report):
        return jsonify({"message": "You cannot view this operational report."}), 403

    if request.method == "GET":
        return jsonify(report.to_dict())

    if not _can_manage_operational_report(report):
        return jsonify({"message": "You cannot edit this operational report."}), 403

    data = request.get_json(silent=True) or {}
    values, error = _validate_operational_report_payload(
        data,
        report.incident,
        existing=report,
    )
    if error:
        return jsonify({"message": error}), 400
    if values["department"] != report.department:
        return jsonify({"message": "The reporting department cannot be changed after creation."}), 400

    previous = {
        "responder_name": report.responder_name,
        "outcome": report.outcome,
        "people_affected": report.people_affected,
        "final_classification": report.final_classification,
        "final_departments": list(report.final_departments or []),
        "completed_at": report.completed_at.isoformat() if report.completed_at else None,
    }
    for key, value in values.items():
        setattr(report, key, value)
    report.updated_by_id = current_user.id
    report.updated_at = datetime.utcnow()

    audit = _create_audit(
        report.incident,
        "OPERATIONAL_REPORT_SAVED",
        previous_status=report.incident.status,
        new_status=report.incident.status,
        previous_departments=_active_department_names(report.incident),
        new_departments=values["final_departments"],
        notes=values["outcome"],
        details={
            "report_id": report.id,
            "report_department": report.department,
            "report_action": "updated",
            "previous": previous,
        },
    )
    db.session.commit()
    socketio.emit("operational_report_changed", {
        "incident_id": report.incident_id,
        "report_id": report.id,
        "change": "updated",
    })
    _emit_audit(audit)
    return jsonify({"message": "operational report updated", "data": report.to_dict()})


@main.route("/api/operational-reports/<int:report_id>/attachments", methods=["POST"])
@login_required
def upload_operational_report_attachments(report_id):
    report = _operational_report_query().filter_by(id=report_id).first_or_404()
    if not _operational_report_visible(report) or not _can_manage_operational_report(report):
        return jsonify({"message": "You cannot upload attachments to this report."}), 403

    files = request.files.getlist("files")
    files = [item for item in files if item and str(item.filename or "").strip()]
    if not files:
        return jsonify({"message": "Select at least one attachment."}), 400
    if len(report.attachments) + len(files) > MAX_OPERATIONAL_ATTACHMENTS:
        return jsonify({
            "message": f"A report may contain at most {MAX_OPERATIONAL_ATTACHMENTS} attachments."
        }), 400

    upload_folder = _operational_upload_folder()
    created_files = []
    attachments = []
    try:
        for storage in files:
            original_name = secure_filename(storage.filename)
            if not original_name or "." not in original_name:
                raise ValueError("Every attachment must have a valid filename and extension.")
            extension = original_name.rsplit(".", 1)[1].lower()
            if extension not in ALLOWED_ATTACHMENT_EXTENSIONS:
                raise ValueError(
                    "Allowed attachment types are PDF, PNG, JPG, WEBP, TXT, DOC and DOCX."
                )

            content = storage.read(MAX_OPERATIONAL_ATTACHMENT_BYTES + 1)
            if len(content) > MAX_OPERATIONAL_ATTACHMENT_BYTES:
                raise ValueError("Each attachment must be 10 MB or smaller.")
            if not content:
                raise ValueError("Empty attachments are not allowed.")

            stored_name = f"{uuid4().hex}.{extension}"
            absolute_path = os.path.join(upload_folder, stored_name)
            with open(absolute_path, "wb") as handle:
                handle.write(content)
            created_files.append(absolute_path)

            attachment = OperationalReportAttachment(
                report_id=report.id,
                original_filename=original_name[:255],
                stored_filename=stored_name,
                mime_type=str(storage.mimetype or "application/octet-stream")[:120],
                size_bytes=len(content),
                uploaded_by_id=current_user.id,
                created_at=datetime.utcnow(),
            )
            db.session.add(attachment)
            attachments.append(attachment)

        audit = _create_audit(
            report.incident,
            "REPORT_ATTACHMENT_UPLOADED",
            previous_status=report.incident.status,
            new_status=report.incident.status,
            previous_departments=_active_department_names(report.incident),
            new_departments=_active_department_names(report.incident),
            details={
                "report_id": report.id,
                "report_department": report.department,
                "filenames": [item.original_filename for item in attachments],
            },
        )
        db.session.commit()
    except ValueError as error:
        db.session.rollback()
        for path in created_files:
            try:
                os.remove(path)
            except OSError:
                pass
        return jsonify({"message": str(error)}), 400
    except Exception:
        db.session.rollback()
        for path in created_files:
            try:
                os.remove(path)
            except OSError:
                pass
        raise

    socketio.emit("operational_report_changed", {
        "incident_id": report.incident_id,
        "report_id": report.id,
        "change": "attachment-uploaded",
    })
    _emit_audit(audit)
    refreshed_report = _operational_report_query().filter_by(id=report.id).first()
    return jsonify({
        "message": "attachments uploaded",
        "items": [item.to_dict() for item in attachments],
        "data": refreshed_report.to_dict() if refreshed_report else report.to_dict(),
    }), 201


@main.route(
    "/api/operational-report-attachments/<int:attachment_id>/download",
    methods=["GET"],
)
@login_required
def download_operational_report_attachment(attachment_id):
    attachment = OperationalReportAttachment.query.options(
        selectinload(OperationalReportAttachment.report)
        .selectinload(OperationalReport.incident)
        .selectinload(Incident.assignments)
    ).filter_by(id=attachment_id).first_or_404()
    if not _operational_report_visible(attachment.report):
        return jsonify({"message": "You cannot download this attachment."}), 403

    return send_from_directory(
        _operational_upload_folder(),
        attachment.stored_filename,
        as_attachment=True,
        download_name=attachment.original_filename,
    )


@main.route("/api/audit-logs", methods=["GET"])
@login_required
def get_audit_logs():
    query = IncidentAudit.query.options(
        selectinload(IncidentAudit.incident).selectinload(Incident.assignments)
    )

    action = str(request.args.get("action", "") or "").strip().upper()
    username = str(request.args.get("user", "") or "").strip()
    status = str(request.args.get("status", "") or "").strip().title()
    channel = str(request.args.get("channel", "") or "").strip().upper()
    incident_text = str(request.args.get("incident_id", "") or "").strip()
    search = str(request.args.get("search", "") or "").strip().lower()
    department = str(request.args.get("department", "") or "").strip().upper()

    date_from = _parse_audit_date(request.args.get("date_from"))
    date_to = _parse_audit_date(request.args.get("date_to"), end_of_day=True)

    if action:
        query = query.filter(IncidentAudit.action == action)
    if username:
        query = query.filter(IncidentAudit.actor_username.ilike(f"%{username}%"))
    if status:
        query = query.filter(or_(
            IncidentAudit.previous_status == status,
            IncidentAudit.new_status == status,
        ))
    if channel:
        query = query.filter(IncidentAudit.reporting_channel == channel)
    if date_from:
        query = query.filter(IncidentAudit.created_at >= date_from)
    if date_to:
        query = query.filter(IncidentAudit.created_at < date_to)

    incident_digits = "".join(character for character in incident_text if character.isdigit())
    if incident_digits:
        query = query.filter(IncidentAudit.incident_id == int(incident_digits))

    records = query.order_by(IncidentAudit.created_at.desc()).limit(2000).all()
    records = [record for record in records if _audit_visible_to_current_user(record)]

    view_department = _requested_view_department()
    if view_department:
        records = [
            record for record in records
            if view_department in set(record.previous_departments or [])
            or view_department in set(record.new_departments or [])
            or (
                record.incident is not None
                and view_department in _active_department_names(record.incident)
            )
        ]

    if department in ALLOWED_DEPARTMENTS:
        records = [
            record for record in records
            if department in set(record.previous_departments or [])
            or department in set(record.new_departments or [])
        ]

    if search:
        def matches(record):
            searchable = " ".join([
                f"RESQ-{record.incident_id:04d}",
                str(record.action or ""),
                str(record.previous_status or ""),
                str(record.new_status or ""),
                " ".join(record.previous_departments or []),
                " ".join(record.new_departments or []),
                str(record.actor_username or ""),
                str(record.actor_role or ""),
                str(record.notes or ""),
                str(record.reporting_channel or ""),
                str(record.resolution_details or ""),
                str(record.sms_error or ""),
            ]).lower()
            return search in searchable

        records = [record for record in records if matches(record)]

    try:
        limit = max(1, min(int(request.args.get("limit", 100)), 500))
        offset = max(0, int(request.args.get("offset", 0)))
    except (TypeError, ValueError):
        return jsonify({"message": "Invalid audit pagination."}), 400

    total = len(records)
    page = records[offset:offset + limit]
    return jsonify({
        "items": [record.to_dict() for record in page],
        "total": total,
        "limit": limit,
        "offset": offset,
    })



@main.route("/api/incidents/<int:incident_id>/notes", methods=["PATCH"])
@login_required
def update_notes(incident_id):
    if not _can_manage_incidents():
        return jsonify({"message": "Dispatcher access is required."}), 403

    incident = _incident_query().filter_by(id=incident_id).first_or_404()
    data = request.get_json(silent=True) or {}

    previous_notes = str(incident.dispatcher_notes or "").strip() or None
    new_notes = str(data.get("dispatcher_notes", "")).strip() or None
    incident.dispatcher_notes = new_notes
    incident.updated_at = datetime.utcnow()

    audit = None
    if previous_notes != new_notes:
        action = (
            "NOTE_CLEARED"
            if previous_notes and not new_notes
            else "NOTE_ADDED"
            if not previous_notes and new_notes
            else "NOTE_UPDATED"
        )
        departments = _active_department_names(incident)
        audit = _create_audit(
            incident,
            action,
            previous_status=incident.status,
            new_status=incident.status,
            previous_departments=departments,
            new_departments=departments,
            notes=new_notes,
            details={"previous_notes": previous_notes},
        )

    db.session.commit()
    incident_data = _serialize_incident(incident)
    socketio.emit("incident_feed_changed", {"incident_id": incident.id, "change": "updated"})
    _emit_audit(audit)
    return jsonify({"message": "notes saved", "data": incident_data})


@main.route("/api/incidents/<int:incident_id>/classification", methods=["PATCH"])
@login_required
def update_classification(incident_id):
    if not _can_manage_incidents():
        return jsonify({"message": "Dispatcher access is required."}), 403

    incident = _incident_query().filter_by(id=incident_id).first_or_404()
    data = request.get_json(silent=True) or {}
    incident_type = str(data.get("incident_type", "")).strip().upper()
    severity = str(data.get("severity", "")).strip().upper()

    if incident_type not in ALLOWED_TYPES:
        return jsonify({"message": "Incident type must be MEDICAL, FIRE or CRIME."}), 400
    if severity not in ALLOWED_SEVERITIES:
        return jsonify({"message": "Severity must be LOW, HIGH or CRITICAL."}), 400

    previous_type = str(incident.incident_type or "").strip().upper() or None
    previous_severity = str(incident.severity or "").strip().upper() or None
    changed = previous_type != incident_type or previous_severity != severity

    incident.incident_type = incident_type
    incident.severity = severity
    incident.classification_status = "Dispatcher Corrected" if changed else "Dispatcher Confirmed"
    incident.updated_at = datetime.utcnow()

    departments = _active_department_names(incident)
    audit = _create_audit(
        incident,
        "CLASSIFICATION_CORRECTED" if changed else "CLASSIFICATION_CONFIRMED",
        previous_status=incident.status,
        new_status=incident.status,
        previous_departments=departments,
        new_departments=departments,
        details={
            "previous_incident_type": previous_type,
            "new_incident_type": incident_type,
            "previous_severity": previous_severity,
            "new_severity": severity,
            "ai_confidence": incident.nlp_confidence,
            "classification_status": incident.classification_status,
        },
    )
    db.session.commit()

    incident_data = _serialize_incident(incident)
    socketio.emit("incident_feed_changed", {"incident_id": incident.id, "change": "updated"})
    _emit_audit(audit)
    return jsonify({"message": "classification updated", "data": incident_data})


@main.route("/api/incidents/<int:incident_id>/assignments", methods=["PATCH"])
@login_required
def update_assignments(incident_id):
    if not _can_manage_incidents():
        return jsonify({"message": "Dispatcher access is required."}), 403

    incident = _incident_query().filter_by(id=incident_id).first_or_404()
    data = request.get_json(silent=True) or {}
    departments = _normalise_departments(data.get("departments", []))
    action = str(data.get("action", "save")).strip().lower()

    if action not in {"save", "dispatch", "escalate"}:
        return jsonify({"message": "Invalid assignment action."}), 400
    if action in {"dispatch", "escalate"} and not departments:
        return jsonify({"message": "Select at least one department."}), 400

    previous_status = str(incident.status or "Pending").strip().title()
    previous_departments = sorted(_active_department_names(incident))
    active_departments = _sync_assignments(incident, departments, current_user.id)
    now = datetime.utcnow()

    if action == "dispatch":
        incident.status = "Dispatched"
        incident.dispatched_at = incident.dispatched_at or now
    elif action == "escalate":
        incident.status = "Escalated"
        incident.dispatched_at = incident.dispatched_at or now

    incident.updated_at = now

    sms_sent = None
    sms_error = None
    sms_attempted = False
    if action == "dispatch" and previous_status.lower() not in {"dispatched", "escalated"}:
        sms_attempted = True
        sms_sent, sms_error = _send_dispatch_sms(incident)

    audit = _create_audit(
        incident,
        {"save": "ASSIGNMENT_UPDATED", "dispatch": "DISPATCHED", "escalate": "ESCALATED"}[action],
        previous_status=previous_status,
        new_status=incident.status,
        previous_departments=previous_departments,
        new_departments=active_departments,
        notes=incident.dispatcher_notes,
        sms_sent=sms_sent,
        sms_error=sms_error,
        details={"sms_attempted": sms_attempted, "assignment_action": action},
    )
    db.session.commit()

    incident_data = _serialize_incident(incident)
    socketio.emit("incident_feed_changed", {"incident_id": incident.id, "change": "updated"})
    _emit_audit(audit)
    return jsonify({
        "message": "assignment updated",
        "departments": active_departments,
        "data": incident_data,
        "sms_sent": sms_sent,
        "sms_error": sms_error,
    })


@main.route("/api/incidents/<int:incident_id>/status", methods=["PATCH"])
@login_required
def update_status(incident_id):
    if not _can_manage_incidents():
        return jsonify({"message": "Dispatcher access is required."}), 403

    incident = _incident_query().filter_by(id=incident_id).first_or_404()
    data = request.get_json(silent=True) or {}
    statuses = {
        "pending": "Pending",
        "dispatched": "Dispatched",
        "escalated": "Escalated",
        "resolved": "Resolved",
    }
    requested = str(data.get("status", "")).strip().lower()
    if requested not in statuses:
        return jsonify({"message": "Invalid incident status."}), 400

    previous_status = str(incident.status or "Pending").strip().title()
    departments = sorted(_active_department_names(incident))
    now = datetime.utcnow()
    incident.status = statuses[requested]

    if "dispatcher_notes" in data:
        incident.dispatcher_notes = str(data.get("dispatcher_notes", "")).strip() or None
    if requested in {"dispatched", "escalated"}:
        incident.dispatched_at = incident.dispatched_at or now
    if requested == "resolved":
        incident.resolved_at = incident.resolved_at or now
    incident.updated_at = now

    sms_sent = None
    sms_error = None
    sms_attempted = False
    if requested == "dispatched" and previous_status.lower() not in {"dispatched", "escalated"}:
        sms_attempted = True
        sms_sent, sms_error = _send_dispatch_sms(incident)

    resolution_details = None
    if requested == "resolved":
        resolution_details = (
            str(data.get("resolution_details", "") or "").strip()
            or incident.dispatcher_notes
        )

    audit = _create_audit(
        incident,
        {
            "pending": "STATUS_UPDATED",
            "dispatched": "DISPATCHED",
            "escalated": "ESCALATED",
            "resolved": "RESOLVED",
        }[requested],
        previous_status=previous_status,
        new_status=incident.status,
        previous_departments=departments,
        new_departments=departments,
        notes=incident.dispatcher_notes,
        resolution_details=resolution_details,
        sms_sent=sms_sent,
        sms_error=sms_error,
        details={"sms_attempted": sms_attempted},
    )
    db.session.commit()

    incident_data = _serialize_incident(incident)
    socketio.emit("incident_feed_changed", {"incident_id": incident.id, "change": "updated"})
    _emit_audit(audit)
    return jsonify({
        "message": "updated",
        "data": incident_data,
        "sms_sent": sms_sent,
        "sms_error": sms_error,
    })
