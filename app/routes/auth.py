import string

from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required

from app import db
from app.models import User

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


@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        # Missing/invalid JSON body - report it like any other missing field
        # instead of crashing with a 500 on data.get().
        data = {}

    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if not name or not email or not password:
        return jsonify({"error": "name, email, and password are required"}), 400

    # This is the real enforcement point - the check in signup.html is UX only,
    # and anyone can call this endpoint directly without the page's JavaScript.
    if not is_valid_password(password):
        return jsonify({"error": PASSWORD_RULE_MESSAGE}), 400

    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({"error": "An account with this email already exists"}), 409

    user = User(name=name, email=email)
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    return jsonify({"message": "Account created successfully", "user_id": user.id}), 201

from flask_login import login_user, logout_user, login_required


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid email or password"}), 401

    login_user(user)
    return jsonify({"message": "Logged in successfully", "user_id": user.id}), 200


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return jsonify({"message": "Logged out successfully"}), 200