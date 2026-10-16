import string

from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app import db, usernames
from app.models import User
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
    return jsonify({"message": "Logged in successfully", "user_id": user.id}), 200


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return jsonify({"message": "Logged out successfully"}), 200