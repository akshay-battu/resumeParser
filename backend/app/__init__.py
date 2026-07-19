import os
from pathlib import Path

from flask import Flask, send_from_directory
from flask_cors import CORS
from sqlalchemy import inspect, text

from app.config import Config
from app.extensions import db
from app.routes.candidates import candidates_bp


def _migrate_schema():
    """Add new columns to existing SQLite DBs without Alembic."""
    inspector = inspect(db.engine)
    if not inspector.has_table("document_requests"):
        return

    existing = {col["name"] for col in inspector.get_columns("document_requests")}
    additions = {
        "recipient": "VARCHAR(255)",
        "send_status": "VARCHAR(32) DEFAULT 'pending'",
        "send_detail": "VARCHAR(512)",
        "sent_at": "DATETIME",
    }
    for column, col_type in additions.items():
        if column not in existing:
            try:
                db.session.execute(text(f"ALTER TABLE document_requests ADD COLUMN {column} {col_type}"))
                db.session.commit()
            except Exception as exc:
                db.session.rollback()
                if "duplicate column" in str(exc).lower() or "already exists" in str(exc).lower():
                    # Safely ignore duplicate column errors if another worker has already added it
                    continue
                raise exc


def _fix_relative_document_paths():
    """Absolutize any stale relative resume/pan/aadhaar paths saved before
    LocalStorageService started resolving to absolute paths — send_file()
    resolves relative paths against the Flask app's root_path, not wherever
    they were actually saved, so a relative path 404s even though the file exists.
    """
    from app.models.candidate import Candidate

    fields = ("resume_path", "pan_path", "aadhaar_path")
    for candidate in Candidate.query.all():
        changed = False
        for field in fields:
            value = getattr(candidate, field)
            if value and not Path(value).is_absolute():
                setattr(candidate, field, str(Path(value).resolve()))
                changed = True
        if changed:
            db.session.add(candidate)
    db.session.commit()


def create_app(config_class=Config):
    app = Flask(__name__, static_folder=None)
    app.config.from_object(config_class)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)

    origins = [o.strip() for o in app.config["CORS_ORIGINS"].split(",") if o.strip()]
    CORS(app, origins=origins)

    app.register_blueprint(candidates_bp, url_prefix="/candidates")

    @app.route("/health")
    def health():
        return {"status": "ok"}

    from app.spa import _frontend_dist

    frontend_dist = _frontend_dist()

    if frontend_dist:

        @app.route("/", defaults={"path": ""})
        @app.route("/<path:path>")
        def serve_frontend(path):
            if path and (frontend_dist / path).exists():
                return send_from_directory(frontend_dist, path)
            return send_from_directory(frontend_dist, "index.html")

    with app.app_context():
        db.create_all()
        _migrate_schema()
        _fix_relative_document_paths()

    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        from app.services.inbox_poller import start_inbox_poller

        start_inbox_poller(app)

    return app
