from datetime import datetime

from app import db, socketio
from app.models.incident import Incident
from app.models.incident_assignment import IncidentAssignment
from app.models.incident_audit import IncidentAudit
from app.models.system_setting import SystemSetting
from app.nlp.triage import triage


class USSDHandler:

    @staticmethod
    def handle_request(session_id, phone_number, text, network):
        """
        Expected USSD text flow:

        1
        1*2
        1*2*Kamwala behind the market
        1*2*Kamwala behind the market*There is a shop on fire

        Entering 0 returns the user to the previous step.
        """

        raw_parts = (
            [part.strip() for part in text.split("*")]
            if text
            else []
        )

        parts = []
        for part in raw_parts:
            if part == "0":
                if parts:
                    parts.pop()
            else:
                parts.append(part)

        if len(parts) == 0:
            return USSDHandler.language_menu(), False

        language = parts[0]
        if language not in {"1", "2"}:
            return "Invalid language option.", True

        if len(parts) == 1:
            return USSDHandler.incident_type_menu(language), False

        incident_type = parts[1]
        if incident_type not in {"1", "2", "3"}:
            return "Invalid emergency type.", True

        if len(parts) == 2:
            return USSDHandler.location_prompt(language, incident_type), False

        location_text = parts[2].strip()
        if not location_text:
            return USSDHandler.location_prompt(language, incident_type), False

        if len(parts) == 3:
            return USSDHandler.description_prompt(language), False

        issue_description = "*".join(parts[3:]).strip()
        if not issue_description:
            return USSDHandler.description_prompt(language), False

        response = USSDHandler.save_incident(
            session_id=session_id,
            phone_number=phone_number,
            language=language,
            incident_type=incident_type,
            location_text=location_text,
            issue_description=issue_description,
            network=network
        )

        return response, True

    @staticmethod
    def language_menu():
        return (
            "ResQ Emergency\n"
            "Select language:\n"
            "1. English\n"
            "2. Nyanja"
        )

    @staticmethod
    def incident_type_menu(language):
        if language == "2":
            return (
                "Sankhani mtundu wa ngozi:\n"
                "1. Medical\n"
                "2. Fire\n"
                "3. Crime\n"
                "0. Back"
            )

        return (
            "Select emergency type:\n"
            "1. Medical\n"
            "2. Fire\n"
            "3. Crime\n"
            "0. Back"
        )

    @staticmethod
    def location_prompt(language, incident_type):
        labels = {
            "1": "medical emergency",
            "2": "fire",
            "3": "crime"
        }
        incident_name = labels.get(incident_type, "emergency")

        if language == "2":
            return (
                f"Kuli kuti {incident_name}? "
                "Lembani malo enieni kapena landmark.\n"
                "Example: Kamwala behind the market.\n"
                "0. Back"
            )

        return (
            f"Where is the {incident_name}? "
            "Enter a specific location or nearby landmark.\n"
            "Example: Kamwala behind the market.\n"
            "0. Back"
        )

    @staticmethod
    def description_prompt(language):
        if language == "2":
            return (
                "Fotokozani mwachidule zomwe zachitika:\n"
                "0. Back"
            )

        return (
            "Briefly explain what has happened:\n"
            "0. Back"
        )

    @staticmethod
    def _type_map():
        return {
            "1": "MEDICAL",
            "2": "FIRE",
            "3": "CRIME"
        }

    @staticmethod
    def _default_departments(selected_type):
        return {
            "MEDICAL": ["MEDICAL"],
            "FIRE": ["FIRE"],
            "CRIME": ["POLICE"]
        }.get(selected_type, [])

    @staticmethod
    def _confidence_threshold():
        try:
            settings = SystemSetting.query.get(1)
            if settings:
                return float(settings.nlp_confidence_threshold or 0.75)
        except Exception:
            pass
        return 0.75

    @staticmethod
    def save_incident(
        session_id,
        phone_number,
        language,
        incident_type,
        location_text,
        issue_description,
        network
    ):
        selected_type = USSDHandler._type_map().get(incident_type, "UNKNOWN")
        saved_language = "ny" if language == "2" else "en"

        raw_text = (
            f"{selected_type} emergency at "
            f"{location_text}. "
            f"Details: {issue_description}"
        )

        try:
            triage_result = triage(raw_text) or {}
        except Exception as error:
            print(f"USSD triage error: {error}")
            triage_result = {
                "severity": "LOW",
                "confidence": 0.0
            }

        severity = str(triage_result.get("severity", "LOW") or "LOW").strip().upper()
        if severity not in {"LOW", "HIGH", "CRITICAL"}:
            severity = "LOW"

        try:
            confidence = float(triage_result.get("confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence > 1:
            confidence = confidence / 100
        confidence = max(0.0, min(confidence, 1.0))

        classification_status = (
            "Caller Selected"
            if confidence >= USSDHandler._confidence_threshold()
            else "Needs Review"
        )

        default_departments = USSDHandler._default_departments(selected_type)
        now = datetime.utcnow()

        try:
            incident = Incident(
                raw_text=raw_text,
                channel="USSD",
                incident_type=selected_type if selected_type != "UNKNOWN" else None,
                severity=severity,
                location=location_text,
                latitude=None,
                longitude=None,
                phone_number=phone_number,
                language=saved_language,
                status="Pending",
                dispatcher_notes=None,
                created_at=now,
                updated_at=now,
                nlp_confidence=confidence,
                classification_status=classification_status,
            )

            db.session.add(incident)
            db.session.flush()

            for department in default_departments:
                db.session.add(
                    IncidentAssignment(
                        incident_id=incident.id,
                        department=department,
                        active=True,
                        assigned_at=now,
                        assigned_by_id=None,
                    )
                )

            db.session.add(
                IncidentAudit(
                    incident_id=incident.id,
                    action="INCIDENT_REPORTED",
                    previous_status=None,
                    new_status="Pending",
                    previous_departments=[],
                    new_departments=default_departments,
                    actor_id=None,
                    actor_username=None,
                    actor_role=None,
                    notes=raw_text,
                    reporting_channel="USSD",
                    sms_sent=None,
                    sms_error=None,
                    details={
                        "ussd_session_id": session_id,
                        "network": network,
                        "readable_location": location_text,
                        "language": saved_language,
                        "caller_selected_type": selected_type,
                        "severity": severity,
                        "confidence": confidence,
                        "classification_status": classification_status,
                        "initial_departments": default_departments,
                    },
                    created_at=now,
                )
            )

            db.session.commit()

            socketio.emit(
                "incident_feed_changed",
                {
                    "incident_id": incident.id,
                    "change": "created"
                }
            )
            socketio.emit(
                "audit_log_created",
                {
                    "incident_id": incident.id,
                    "change": "created"
                }
            )

            if language == "2":
                return (
                    "Lipoti lanu lalandiridwa. "
                    "ResQ dispatch yadziwitsidwa. "
                    "Tidzakuyankhani posachedwa. "
                    f"Reference: RESQ-{incident.id:04d}"
                )

            return (
                "Your emergency report has been received. "
                "ResQ dispatch has been alerted. "
                "We will contact you and get to you soon. "
                f"Reference: RESQ-{incident.id:04d}"
            )

        except Exception as error:
            db.session.rollback()
            print(f"USSD database error: {error}")

            if language == "2":
                return "Lipoti silinasungidwe. Yesaninso."

            return "Your report could not be saved. Please try again."
