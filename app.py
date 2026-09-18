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


def create_app():

    app = Flask(__name__)

    app.config.from_object(Config)

    # Database
    db.init_app(app)

    # Login
    login_manager = LoginManager()

    login_manager.login_view = "auth.login"

    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):

        return db.session.get(User, user_id)

    # Routes
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

            return {"status": "ok", "database": "connected"}

        except Exception as e:
            return {
                "status": "error",
                "database": "disconnected",
                "message": str(e),
            }, 500

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=app.config["DEBUG"])
