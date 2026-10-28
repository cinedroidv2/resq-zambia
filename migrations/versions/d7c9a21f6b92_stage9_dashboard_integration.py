"""stage 9 dashboard integration tables and user settings

Revision ID: d7c9a21f6b92
Revises: f31ab68cff36
Create Date: 2026-06-15 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
import json


revision = "d7c9a21f6b92"
down_revision = "f31ab68cff36"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("department", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("full_name", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("phone_number", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("profile_image_filename", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("last_login_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("current_session_started_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("created_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))
        batch_op.create_index("ix_users_department", ["department"], unique=False)

    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE users SET "
            "department = CASE "
            "WHEN lower(role) = 'police' THEN 'POLICE' "
            "WHEN lower(role) = 'fire' THEN 'FIRE' "
            "WHEN lower(role) = 'medical' THEN 'MEDICAL' "
            "WHEN lower(role) = 'admin' THEN 'OPERATIONS' "
            "ELSE 'DISPATCH' END, "
            "created_at = COALESCE(created_at, CURRENT_TIMESTAMP), "
            "updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)"
        )
    )

    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("theme", sa.String(length=12), nullable=False),
        sa.Column("auto_refresh_seconds", sa.Integer(), nullable=False),
        sa.Column("critical_sound_enabled", sa.Boolean(), nullable=False),
        sa.Column("desktop_notifications_enabled", sa.Boolean(), nullable=False),
        sa.Column("map_show_incidents", sa.Boolean(), nullable=False),
        sa.Column("map_show_facilities", sa.Boolean(), nullable=False),
        sa.Column("map_show_heat", sa.Boolean(), nullable=False),
        sa.Column("map_cluster_incidents", sa.Boolean(), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("theme IN ('dark', 'light', 'system')", name="ck_user_preferences_theme"),
        sa.CheckConstraint("auto_refresh_seconds IN (0, 5, 10, 15, 30, 60)", name="ck_user_preferences_refresh"),
        sa.CheckConstraint("language IN ('en', 'ny')", name="ck_user_preferences_language"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_user_preferences_user_id", "user_preferences", ["user_id"], unique=False)

    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nlp_confidence_threshold", sa.Float(), nullable=False),
        sa.Column("default_refresh_seconds", sa.Integer(), nullable=False),
        sa.Column("default_language", sa.String(length=8), nullable=False),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("nlp_confidence_threshold >= 0.50 AND nlp_confidence_threshold <= 0.95", name="ck_system_setting_nlp_threshold"),
        sa.CheckConstraint("default_refresh_seconds IN (0, 5, 10, 15, 30, 60)", name="ck_system_setting_refresh"),
        sa.CheckConstraint("default_language IN ('en', 'ny')", name="ck_system_setting_language"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "facilities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("department", sa.String(length=20), nullable=False),
        sa.Column("readable_location", sa.String(length=255), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("coverage_area", sa.String(length=255), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("department IN ('POLICE', 'FIRE', 'MEDICAL')", name="ck_facility_department"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_facilities_active", "facilities", ["active"], unique=False)
    op.create_index("ix_facilities_department", "facilities", ["department"], unique=False)

    op.create_table(
        "incident_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("department", sa.String(length=20), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("assigned_by_id", sa.Integer(), nullable=True),
        sa.Column("removed_by_id", sa.Integer(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(), nullable=True),
        sa.Column("removed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("department IN ('POLICE', 'FIRE', 'MEDICAL')", name="ck_incident_assignment_department"),
        sa.ForeignKeyConstraint(["assigned_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["removed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incident_assignments_active", "incident_assignments", ["active"], unique=False)
    op.create_index("ix_incident_assignments_department", "incident_assignments", ["department"], unique=False)
    op.create_index("ix_incident_assignments_incident_id", "incident_assignments", ["incident_id"], unique=False)

    op.create_table(
        "incident_audits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("previous_status", sa.String(length=30), nullable=True),
        sa.Column("new_status", sa.String(length=30), nullable=True),
        sa.Column("previous_departments", sa.JSON(), nullable=True),
        sa.Column("new_departments", sa.JSON(), nullable=True),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_username", sa.String(length=80), nullable=True),
        sa.Column("actor_role", sa.String(length=32), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("reporting_channel", sa.String(length=20), nullable=True),
        sa.Column("resolution_details", sa.Text(), nullable=True),
        sa.Column("sms_sent", sa.Boolean(), nullable=True),
        sa.Column("sms_error", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incident_audits_action", "incident_audits", ["action"], unique=False)
    op.create_index("ix_incident_audits_actor_username", "incident_audits", ["actor_username"], unique=False)
    op.create_index("ix_incident_audits_created_at", "incident_audits", ["created_at"], unique=False)
    op.create_index("ix_incident_audits_incident_id", "incident_audits", ["incident_id"], unique=False)

    connection = op.get_bind()
    now = sa.func.current_timestamp()
    rows = connection.execute(
        sa.text(
            "SELECT id, incident_type, assigned_departments, status, raw_text, "
            "channel, created_at FROM incidents"
        )
    ).mappings().all()

    type_department_map = {
        "CRIME": ["POLICE"],
        "FIRE": ["FIRE"],
        "MEDICAL": ["MEDICAL"],
    }

    for row in rows:
        departments = []
        legacy_departments = row.get("assigned_departments")
        if legacy_departments:
            try:
                parsed = json.loads(legacy_departments)
                if isinstance(parsed, list):
                    for item in parsed:
                        department = str(item or "").strip().upper()
                        if department in {"POLICE", "FIRE", "MEDICAL"} and department not in departments:
                            departments.append(department)
            except (TypeError, ValueError):
                departments = []

        if not departments:
            departments = type_department_map.get(str(row.get("incident_type") or "").strip().upper(), [])

        for department in departments:
            connection.execute(
                sa.text(
                    "INSERT INTO incident_assignments "
                    "(incident_id, department, active, assigned_at) "
                    "VALUES (:incident_id, :department, 1, CURRENT_TIMESTAMP)"
                ),
                {"incident_id": row["id"], "department": department},
            )

        connection.execute(
            sa.text(
                "INSERT INTO incident_audits "
                "(incident_id, action, previous_status, new_status, previous_departments, "
                "new_departments, actor_id, actor_username, actor_role, notes, "
                "reporting_channel, details, created_at) "
                "VALUES (:incident_id, 'MIGRATED_EXISTING_INCIDENT', NULL, :new_status, "
                ":previous_departments, :new_departments, NULL, NULL, NULL, :notes, "
                ":channel, :details, CURRENT_TIMESTAMP)"
            ),
            {
                "incident_id": row["id"],
                "new_status": row.get("status") or "Pending",
                "previous_departments": json.dumps([]),
                "new_departments": json.dumps(departments),
                "notes": row.get("raw_text"),
                "channel": row.get("channel"),
                "details": json.dumps({"source": "stage9_migration"}),
            },
        )

    connection.execute(
        sa.text(
            "INSERT INTO system_settings "
            "(id, nlp_confidence_threshold, default_refresh_seconds, default_language, created_at, updated_at) "
            "VALUES (1, 0.75, 10, 'en', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
    )

    op.create_table(
        "department_resources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("department", sa.String(length=20), nullable=False),
        sa.Column("resource_type", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("identifier", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("facility_id", sa.Integer(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("last_updated_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("department IN ('POLICE', 'FIRE', 'MEDICAL')", name="ck_department_resource_department"),
        sa.CheckConstraint("resource_type IN ('PERSONNEL', 'VEHICLE', 'EQUIPMENT')", name="ck_department_resource_type"),
        sa.CheckConstraint("status IN ('AVAILABLE', 'DISPATCHED', 'UNAVAILABLE', 'MAINTENANCE')", name="ck_department_resource_status"),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["last_updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_department_resources_department", "department_resources", ["department"], unique=False)
    op.create_index("ix_department_resources_facility_id", "department_resources", ["facility_id"], unique=False)
    op.create_index("ix_department_resources_resource_type", "department_resources", ["resource_type"], unique=False)
    op.create_index("ix_department_resources_status", "department_resources", ["status"], unique=False)

    op.create_table(
        "operational_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("department", sa.String(length=20), nullable=False),
        sa.Column("responder_name", sa.String(length=160), nullable=False),
        sa.Column("findings", sa.Text(), nullable=False),
        sa.Column("actions_taken", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("people_affected", sa.Integer(), nullable=False),
        sa.Column("resources_used", sa.Text(), nullable=True),
        sa.Column("final_classification", sa.String(length=20), nullable=False),
        sa.Column("final_departments", sa.JSON(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("department IN ('POLICE', 'FIRE', 'MEDICAL')", name="ck_operational_report_department"),
        sa.CheckConstraint("final_classification IN ('MEDICAL', 'FIRE', 'CRIME')", name="ck_operational_report_final_classification"),
        sa.CheckConstraint("people_affected >= 0", name="ck_operational_report_people_affected"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("incident_id", "department", name="uq_operational_report_incident_department"),
    )
    op.create_index("ix_operational_reports_created_by_id", "operational_reports", ["created_by_id"], unique=False)
    op.create_index("ix_operational_reports_department", "operational_reports", ["department"], unique=False)
    op.create_index("ix_operational_reports_incident_id", "operational_reports", ["incident_id"], unique=False)

    op.create_table(
        "operational_report_attachments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["report_id"], ["operational_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stored_filename"),
    )
    op.create_index("ix_operational_report_attachments_report_id", "operational_report_attachments", ["report_id"], unique=False)


def downgrade():
    op.drop_index("ix_operational_report_attachments_report_id", table_name="operational_report_attachments")
    op.drop_table("operational_report_attachments")

    op.drop_index("ix_operational_reports_incident_id", table_name="operational_reports")
    op.drop_index("ix_operational_reports_department", table_name="operational_reports")
    op.drop_index("ix_operational_reports_created_by_id", table_name="operational_reports")
    op.drop_table("operational_reports")

    op.drop_index("ix_department_resources_status", table_name="department_resources")
    op.drop_index("ix_department_resources_resource_type", table_name="department_resources")
    op.drop_index("ix_department_resources_facility_id", table_name="department_resources")
    op.drop_index("ix_department_resources_department", table_name="department_resources")
    op.drop_table("department_resources")

    op.drop_index("ix_incident_audits_incident_id", table_name="incident_audits")
    op.drop_index("ix_incident_audits_created_at", table_name="incident_audits")
    op.drop_index("ix_incident_audits_actor_username", table_name="incident_audits")
    op.drop_index("ix_incident_audits_action", table_name="incident_audits")
    op.drop_table("incident_audits")

    op.drop_index("ix_incident_assignments_incident_id", table_name="incident_assignments")
    op.drop_index("ix_incident_assignments_department", table_name="incident_assignments")
    op.drop_index("ix_incident_assignments_active", table_name="incident_assignments")
    op.drop_table("incident_assignments")

    op.drop_index("ix_facilities_department", table_name="facilities")
    op.drop_index("ix_facilities_active", table_name="facilities")
    op.drop_table("facilities")

    op.drop_table("system_settings")

    op.drop_index("ix_user_preferences_user_id", table_name="user_preferences")
    op.drop_table("user_preferences")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index("ix_users_department")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("created_at")
        batch_op.drop_column("current_session_started_at")
        batch_op.drop_column("last_login_at")
        batch_op.drop_column("profile_image_filename")
        batch_op.drop_column("phone_number")
        batch_op.drop_column("full_name")
        batch_op.drop_column("department")
