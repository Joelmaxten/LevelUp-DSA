import os
import secrets

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
    config_class = config[config_name]
    if hasattr(config_class, "validate"):
        config_class.validate()
    app.config.from_object(config_class)

    # The resume upload folder is git-ignored, so a fresh clone does not have it.
    try:
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    except OSError:
        pass  # a read-only disk: uploads will report their own error

    from app.security import init_security
    init_security(app)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = None

    # New for every server start (see LOGOUT_ON_RESTART in config.py).
    app.config["BOOT_ID"] = secrets.token_hex(8)

    @app.before_request
    def drop_login_from_an_earlier_run():
        from flask import session
        from flask_login import current_user, logout_user
        if (app.config.get("LOGOUT_ON_RESTART") and current_user.is_authenticated
                and session.get("boot_id") != app.config["BOOT_ID"]):
            logout_user()
            session.pop("boot_id", None)

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

    from app.routes.career_paths import career_paths_bp
    app.register_blueprint(career_paths_bp)

    from app.routes.resume import resume_bp
    app.register_blueprint(resume_bp)

    from app.routes.dashboard import dashboard_bp, user_has_saved_work
    app.register_blueprint(dashboard_bp)

    from app.routes.scenarios import scenarios_bp
    app.register_blueprint(scenarios_bp)

    from app.routes.readiness import readiness_bp
    app.register_blueprint(readiness_bp)

    from app.routes.gamification import gamification_bp
    app.register_blueprint(gamification_bp)

    from app.routes.profile import profile_bp
    app.register_blueprint(profile_bp)

    from functools import wraps

    from flask import redirect, render_template, request, url_for
    from flask_login import current_user

    # Pages a successful login may send the user on to (via ?next=). An
    # allowlist rather than "any local path", so /login?next=... can never be
    # turned into an open redirect.
    POST_LOGIN_PAGES = {"/dashboard", "/quiz", "/conversation", "/roadmap", "/resume", "/scenarios", "/profile"}
    # Where a plain login (no ?next=) goes. /dashboard shows a returning user's
    # saved results, and sends a brand-new user (nothing saved yet) to the home
    # page, where all the phases are offered side by side.
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
        # The dashboard link is only useful once there is something on it.
        has_saved_work = current_user.is_authenticated and user_has_saved_work(current_user.id)
        return render_template("index.html", has_saved_work=has_saved_work)

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
        # Always renders for a logged-in user. A brand-new account gets the empty states and the Placement
        # Readiness card (0.0 / 100) instead of a silent bounce to the home page.
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

    @app.route("/scenarios", methods=["GET"])
    @page_login_required
    def scenarios_page():
        return render_template("scenarios.html")

    @app.route("/profile", methods=["GET"])
    @page_login_required
    def profile_page():
        return render_template("profile.html")

    # Friendly error pages. A browser asking for a page gets the styled page; anything else (the app's fetch()
    # calls, scripts) gets a small fixed JSON body, so API callers never receive HTML. The status code is kept.
    def wants_html():
        best = request.accept_mimetypes.best_match(["application/json", "text/html"])
        return request.method == "GET" and best == "text/html"

    @app.errorhandler(404)
    def not_found(_error):
        if wants_html():
            return render_template("error.html", code=404, title="Page not found",
                                   message="We couldn't find that page. It may have moved, or the link may be mistyped."), 404
        return {"error": "not_found"}, 404

    @app.errorhandler(500)
    def server_error(_error):
        db.session.rollback()
        if wants_html():
            return render_template("error.html", code=500, title="Something went wrong",
                                   message="That's on us, not you. Please try again in a moment."), 500
        return {"error": "server_error"}, 500

    @app.route("/db-check")
    def db_check():
        from sqlalchemy import text
        try:
            db.session.execute(text("SELECT 1"))
            return "<h1>Database connection: OK</h1>"
        except Exception:
            app.logger.exception("db-check failed")
            return "<h1>Database connection FAILED</h1>", 500

    return app