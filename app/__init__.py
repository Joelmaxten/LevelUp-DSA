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
    login_manager.login_view = None

    @login_manager.unauthorized_handler
    def unauthorized():
        from flask import jsonify
        return jsonify({"error": "Authentication required"}), 401

    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp)

    from app.routes.quiz import quiz_bp
    app.register_blueprint(quiz_bp)


    from app.routes.conversation import conversation_bp
    app.register_blueprint(conversation_bp)

    from app.routes.roadmap import roadmap_bp
    app.register_blueprint(roadmap_bp)

    from app.routes.resume import resume_bp
    app.register_blueprint(resume_bp)

    from app.routes.dashboard import dashboard_bp, user_has_saved_work
    app.register_blueprint(dashboard_bp)
    
    from functools import wraps

    from flask import redirect, render_template, request, url_for
    from flask_login import current_user

    # Pages a successful login may send the user on to (via ?next=). An
    # allowlist rather than "any local path", so /login?next=... can never be
    # turned into an open redirect.
    POST_LOGIN_PAGES = {"/dashboard", "/quiz", "/conversation", "/roadmap", "/resume"}
    # Where a plain login (no ?next=) goes. /dashboard shows a returning user's
    # saved results, and sends a brand-new user (nothing saved yet) on to /quiz.
    DEFAULT_POST_LOGIN_PAGE = "/dashboard"

    def post_login_target():
        next_url = request.args.get("next")
        return next_url if next_url in POST_LOGIN_PAGES else DEFAULT_POST_LOGIN_PAGE

    def page_login_required(view):
        """
        Login gate for HTML pages: redirects to /login (remembering where the
        user was headed) instead of returning the JSON 401 that the API
        routes' @login_required gives via unauthorized_handler above.
        """
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("login_page", next=request.path))
            return view(*args, **kwargs)
        return wrapper

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/signup", methods=["GET"])
    def signup_page():
        if current_user.is_authenticated:
            return redirect(DEFAULT_POST_LOGIN_PAGE)
        return render_template("signup.html")

    @app.route("/login", methods=["GET"])
    def login_page():
        if current_user.is_authenticated:
            return redirect(post_login_target())
        return render_template(
            "login.html",
            next_url=post_login_target(),
            registered=request.args.get("registered") == "1",
        )

    @app.route("/dashboard", methods=["GET"])
    @page_login_required
    def dashboard_page():
        # Nothing saved yet = a first-time user: keep the normal first-time flow
        # (start at the quiz) rather than showing an empty dashboard.
        if not user_has_saved_work(current_user.id):
            return redirect("/quiz")
        return render_template("dashboard.html")

    @app.route("/quiz", methods=["GET"])
    @page_login_required
    def quiz_page():
        return render_template("quiz.html")

    @app.route("/conversation", methods=["GET"])
    @page_login_required
    def conversation_page():
        return render_template("conversation.html")

    @app.route("/roadmap", methods=["GET"])
    @page_login_required
    def roadmap_page():
        return render_template("roadmap.html")

    @app.route("/resume", methods=["GET"])
    @page_login_required
    def resume_page():
        return render_template("resume.html")

    @app.route("/db-check")
    def db_check():
        from sqlalchemy import text
        try:
            db.session.execute(text("SELECT 1"))
            return "<h1>Database connection: OK</h1>"
        except Exception as e:
            return f"<h1>Database connection FAILED</h1><p>{e}</p>"

    return app