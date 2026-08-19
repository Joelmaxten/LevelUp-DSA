import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

from app.config import config

db = SQLAlchemy()
login_manager = LoginManager()


def create_app(config_name=None):
    """Flask application factory."""
    app = Flask(__name__)

    config_name = config_name or os.environ.get("FLASK_ENV", "default")
    app.config.from_object(config[config_name])

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    # Blueprints are registered here as each route module comes online.
    # Left commented until each route file has a working Blueprint (Day 13+).
    # from app.routes.auth import auth_bp
    # app.register_blueprint(auth_bp)

    @app.route("/")
    def index():
        return "<h1>LevelUp DSA</h1><p>App factory is running.</p>"

    @app.route("/db-check")
    def db_check():
        from sqlalchemy import text
        try:
            db.session.execute(text("SELECT 1"))
            return "<h1>Database connection: OK</h1>"
        except Exception as e:
            return f"<h1>Database connection FAILED</h1><p>{e}</p>"

    return app