from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from dotenv import load_dotenv
import os
from flask_socketio import SocketIO

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode="eventlet"
)

login_manager = LoginManager()
login_manager.login_view = "main.login"


@login_manager.user_loader
def load_user(user_id):
    from app.models.user import User
    return User.query.get(int(user_id))


def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL",
        "sqlite:///resq.db"
    )

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Used by profile images and operational-report attachments.
    app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024

    db.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app)
    login_manager.init_app(app)

    # Import every model before db.create_all() and before migrations inspect metadata.
    # This is app/__init__.py. Do not confuse it with app/models/__init__.py.
    from app.models.user import User
    from app.models.user_preference import UserPreference
    from app.models.system_setting import SystemSetting
    from app.models.incident import Incident
    from app.models.incident_assignment import IncidentAssignment
    from app.models.incident_audit import IncidentAudit
    from app.models.facility import Facility
    from app.models.department_resource import DepartmentResource
    from app.models.operational_report import OperationalReport
    from app.models.operational_report_attachment import OperationalReportAttachment

    # Main application routes
    from app.routes import main

    # USSD callback route
    from app.routes.ussd_route import ussd_bp

    app.register_blueprint(main)
    app.register_blueprint(ussd_bp)

    os.makedirs(
        os.path.join(app.instance_path, "uploads", "profile_images"),
        exist_ok=True
    )
    os.makedirs(
        os.path.join(app.instance_path, "uploads", "operational_reports"),
        exist_ok=True
    )

    with app.app_context():
        # Do not call db.create_all() here. The database structure is managed
        # by Flask-Migrate/Alembic so final integration does not collide with
        # migrations. This seeding block is deliberately wrapped so the app can
        # still import before `flask db upgrade` is run.
        try:
            admin = User.query.filter_by(username="admin").first()

            if not admin:
                from werkzeug.security import generate_password_hash

                admin = User(
                    username="admin",
                    password_hash=generate_password_hash("admin123"),
                    role="admin",
                    department="OPERATIONS",
                    full_name="System Administrator"
                )
                db.session.add(admin)
                db.session.flush()
            else:
                changed = False
                if not getattr(admin, "department", None):
                    admin.department = "OPERATIONS"
                    changed = True
                if not getattr(admin, "full_name", None):
                    admin.full_name = "System Administrator"
                    changed = True
                if changed:
                    db.session.add(admin)

            if admin and not getattr(admin, "preferences", None):
                db.session.add(UserPreference(user_id=admin.id))

            if not SystemSetting.query.get(1):
                db.session.add(
                    SystemSetting(
                        id=1,
                        nlp_confidence_threshold=0.75,
                        default_refresh_seconds=10,
                        default_language="en"
                    )
                )

            db.session.commit()

        except Exception as error:
            # This normally means migrations have not been run yet.
            # The app factory should not crash before `flask db upgrade`.
            db.session.rollback()
            app.logger.warning(
                "Startup seed skipped until migrations are applied: %s",
                error
            )

    return app
