from flask import Flask, redirect, url_for
from flask_login import LoginManager

from config import Config
from database import db
from models.user import User
from models.file import File
from models.file_access import FileAccess
from routes.auth import auth_bp
from routes.files import files_bp
from routes.file_access import file_access_bp
from services.kms_client import SKLMClient


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, user_id)

    app.extensions["sklm_client"] = SKLMClient(
        base_url=app.config["SKLM_BASE_URL"],
        username=app.config.get("SKLM_USERNAME"),
        password=app.config.get("SKLM_PASSWORD"),
        verify_tls=app.config["SKLM_VERIFY_TLS"],
        connect_timeout=app.config["SKLM_CONNECT_TIMEOUT"],
        read_timeout=app.config["SKLM_READ_TIMEOUT"],
    )

    app.register_blueprint(auth_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(file_access_bp)

    @app.route("/")
    def index():
        return redirect(url_for("files.files"))

    @app.route("/health")
    def health():
        try:
            from sqlalchemy import text
            db.session.execute(text("SELECT 1"))
            return {
                "status": "ok",
                "database": "connected",
                "sklm_configured": app.extensions["sklm_client"].configured,
            }
        except Exception as exc:
            return {
                "status": "error",
                "database": "disconnected",
                "message": str(exc),
            }, 500

    @app.route("/ready")
    def ready():
        client = app.extensions["sklm_client"]
        if not client.configured:
            return {"status": "not_ready", "sklm": "not_configured"}, 503
        if not app.config.get("SKLM_KEK_ID"):
            return {"status": "not_ready", "sklm": "missing_kek_id"}, 503
        if not client.health():
            return {"status": "not_ready", "sklm": "unreachable"}, 503
        try:
            key = client.get_key(app.config["SKLM_KEK_ID"])
        except Exception:
            return {"status": "not_ready", "sklm": "kek_unavailable"}, 503
        return {
            "status": "ready",
            "sklm": "connected",
            "kek_id": key.get("key_id", app.config["SKLM_KEK_ID"]),
            "kek_status": key.get("status"),
            "kek_algorithm": key.get("algorithm"),
        }

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=app.config["DEBUG"])
