import hashlib
import secrets
import string
import threading
from datetime import datetime, timedelta

from flask import Blueprint, current_app, jsonify, render_template, request, session
from flask_login import login_user, logout_user, login_required
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app import db, mailer, usernames
from app.models import PasswordResetToken, User
from app.security import rate_limit_hit, rate_limited_response

auth_bp = Blueprint("auth", __name__)

MIN_PASSWORD_LENGTH = 8

# Shown verbatim by signup.html's client-side check too - keep the two in sync.
# Names all five requirements so a rejected user can see exactly what's missing.
PASSWORD_RULE_MESSAGE = (
    "Password must be at least 8 characters long and include at least one "
    "uppercase letter, one lowercase letter, one number, and one special "
    "character (such as ! @ # $ %)."
)


def is_valid_password(password):
    """
    At least MIN_PASSWORD_LENGTH characters, with at least one uppercase letter,
    one lowercase letter, one digit, and one special character.

    Every class is an explicit ASCII set (string.ascii_uppercase / ascii_lowercase /
    digits / punctuation) rather than "anything that looks like a letter" or
    "anything that isn't alphanumeric", so the browser-side check can use the
    identical sets and the two can't disagree on edge cases (spaces, accented
    letters, ...). Consequence: a non-ASCII letter like "E" with an acute accent
    counts as none of the four classes - it satisfies the length rule only.
    """
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
        return False
    has_upper = any(c in string.ascii_uppercase for c in password)
    has_lower = any(c in string.ascii_lowercase for c in password)
    has_digit = any(c in string.digits for c in password)
    has_special = any(c in string.punctuation for c in password)
    return has_upper and has_lower and has_digit and has_special


def _username_taken(username, except_user_id=None):
    query = User.query.filter(User.username == username)
    if except_user_id is not None:
        query = query.filter(User.id != except_user_id)
    return db.session.query(query.exists()).scalar()


def _client_key():
    return request.remote_addr or "unknown"


@auth_bp.route("/signup/username-check", methods=["GET"])
def username_check():
    """
    {"available": bool, "error": message or None} for the signup page's live check. Rate-limited per IP address
    (60 a minute), because it says whether a username exists.
    """
    allowed, retry_after = rate_limit_hit("username_check", _client_key(), 60, 60)
    if not allowed:
        return rate_limited_response(retry_after)
    username = usernames.normalize(request.args.get("username"))
    if not usernames.is_valid(username):
        return jsonify({"available": False, "error": usernames.USERNAME_RULE_MESSAGE}), 200
    if _username_taken(username):
        return jsonify({"available": False, "error": "That username is taken. Try another."}), 200
    return jsonify({"available": True, "error": None}), 200


@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        # Missing/invalid JSON body - report it like any other missing field
        # instead of crashing with a 500 on data.get().
        data = {}

    email = data.get("email")
    password = data.get("password")
    if isinstance(email, str):
        email = email.strip()

    if not email or not password or not isinstance(email, str):
        return jsonify({"error": "username, email, and password are required"}), 400

    # The signup page always sends a username. An older API client (and the older smoke tests) may send only
    # "name"; that account gets a username built from the email, which the student can change on the profile page.
    raw_username = data.get("username")
    if raw_username is not None:
        username = usernames.normalize(raw_username)
        if not usernames.is_valid(username):
            return jsonify({"error": usernames.USERNAME_RULE_MESSAGE}), 400
    elif data.get("name"):
        username = None
    else:
        return jsonify({"error": "username, email, and password are required"}), 400

    # This is the real enforcement point - the check in signup.html is UX only,
    # and anyone can call this endpoint directly without the page's JavaScript.
    if not is_valid_password(password):
        return jsonify({"error": PASSWORD_RULE_MESSAGE}), 400

    if User.query.filter(func.lower(User.email) == email.lower()).first():
        return jsonify({"error": "An account with this email already exists"}), 409
    if username is not None and _username_taken(username):
        return jsonify({"error": "That username is taken. Try another."}), 409
    if username is None:
        username = usernames.suggest_from_email(email, _username_taken)

    name = data.get("name") if isinstance(data.get("name"), str) and data.get("name").strip() else username
    user = User(name=name.strip()[:120], username=username, email=email)
    user.set_password(password)

    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        # Two signups raced for the same username or email; the unique index decided.
        db.session.rollback()
        return jsonify({"error": "That username or email was just taken. Try another."}), 409

    return jsonify({"message": "Account created successfully", "user_id": user.id, "username": username}), 201


def find_user_for_login(identifier):
    """An email (contains "@", matched without case) or a username (stored lowercase). None if no such account."""
    identifier = identifier.strip()
    if "@" in identifier:
        return User.query.filter(func.lower(User.email) == identifier.lower()).order_by(User.id).first()
    return User.query.filter(User.username == identifier.lower()).first()


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}

    # "login" is the page's "Username or email" box; "email" is still accepted from older clients.
    identifier = data.get("login") or data.get("email")
    password = data.get("password")

    if not identifier or not password or not isinstance(identifier, str) or not isinstance(password, str):
        return jsonify({"error": "username or email, and password, are required"}), 400

    user = find_user_for_login(identifier)

    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid username/email or password"}), 401

    login_user(user)
    session["boot_id"] = current_app.config["BOOT_ID"]
    return jsonify({"message": "Logged in successfully", "user_id": user.id}), 200


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return jsonify({"message": "Logged out successfully"}), 200


# ---------------------------------------------------------------------------------------------------------------------
# Forgot password: email a single-use, expiring link; the link opens a page that sets a new password.
# ---------------------------------------------------------------------------------------------------------------------

FORGOT_REPLY = "If an account exists for that email, we have sent a link to reset the password. It works for {minutes} minutes."


def _token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def find_valid_reset_token(token):
    """The unused, unexpired PasswordResetToken row for this link token, or None."""
    if not isinstance(token, str) or not 20 <= len(token) <= 200:
        return None
    row = PasswordResetToken.query.filter_by(token_hash=_token_hash(token)).first()
    if row is None or row.used_at is not None or row.expires_at <= datetime.utcnow():
        return None
    return row


def _reset_link(token):
    base = current_app.config.get("APP_BASE_URL") or request.host_url.rstrip("/")
    return f"{base}/reset-password?token={token}"


def _deliver_reset_email(app, address, link, minutes):
    body = (
        "Hi,\n\nSomeone asked to reset the password for your LevelUp DSA account.\n"
        f"Open this link within {minutes} minutes to choose a new password:\n\n{link}\n\n"
        "If this was not you, ignore this email; your password stays the same.\n"
    )
    with app.app_context():
        mailer.send_email(app.config, address, "Reset your LevelUp DSA password", body, debug=app.debug)


@auth_bp.route("/forgot-password", methods=["GET"])
def forgot_password_page():
    return render_template("forgot_password.html")


@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    """Always answers the same way, so the page cannot be used to find out which emails have accounts."""
    minutes = current_app.config["PASSWORD_RESET_TTL_MIN"]
    reply = jsonify({"message": FORGOT_REPLY.format(minutes=minutes)})

    data = request.get_json(silent=True)
    email = data.get("email") if isinstance(data, dict) else None
    if not isinstance(email, str) or "@" not in email or len(email) > 120:
        return jsonify({"error": "Enter the email address you signed up with."}), 400
    email = email.strip().lower()

    ok, retry = rate_limit_hit("forgot_ip", _client_key(), 10, 3600)
    if ok:
        ok, retry = rate_limit_hit("forgot_email", email, 3, 3600)
    if not ok:
        return rate_limited_response(retry)

    user = User.query.filter(func.lower(User.email) == email).order_by(User.id).first()
    if user is None:
        return reply

    now = datetime.utcnow()
    # A new request replaces earlier links: only the newest one works.
    PasswordResetToken.query.filter(PasswordResetToken.user_id == user.id,
                                    PasswordResetToken.used_at.is_(None)).update({"used_at": now})
    token = secrets.token_urlsafe(32)
    db.session.add(PasswordResetToken(user_id=user.id, token_hash=_token_hash(token),
                                      expires_at=now + timedelta(minutes=minutes)))
    db.session.commit()

    app = current_app._get_current_object()
    args = (app, user.email, _reset_link(token), minutes)
    if app.config.get("MAIL_ASYNC", True):
        threading.Thread(target=_deliver_reset_email, args=args, daemon=True).start()
    else:
        _deliver_reset_email(*args)
    return reply


@auth_bp.route("/reset-password", methods=["GET"])
def reset_password_page():
    token = request.args.get("token", "")
    resp = current_app.make_response(render_template(
        "reset_password.html", token=token, token_ok=find_valid_reset_token(token) is not None,
        password_rule=PASSWORD_RULE_MESSAGE))
    resp.headers["Referrer-Policy"] = "no-referrer"   # the token is in the address; do not leak it to other sites
    resp.headers["Cache-Control"] = "no-store"
    return resp


@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    ok, retry = rate_limit_hit("reset_ip", _client_key(), 20, 3600)
    if not ok:
        return rate_limited_response(retry)

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    token, password = data.get("token"), data.get("password")
    if not isinstance(password, str) or not password:
        return jsonify({"error": "Enter a new password."}), 400
    if not is_valid_password(password):
        return jsonify({"error": PASSWORD_RULE_MESSAGE}), 400

    row = find_valid_reset_token(token)
    if row is None:
        return jsonify({"error": "This reset link is invalid or has expired. Request a new one."}), 400

    user = db.session.get(User, row.user_id)
    user.set_password(password)
    now = datetime.utcnow()
    PasswordResetToken.query.filter(PasswordResetToken.user_id == user.id,
                                    PasswordResetToken.used_at.is_(None)).update({"used_at": now})
    db.session.commit()
    return jsonify({"message": "Password updated. You can log in with the new password."}), 200

