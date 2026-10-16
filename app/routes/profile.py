"""
The student's own profile: personal details, username, profile picture and password change.

Every route works on current_user only (there is no way to read or change another student's profile). Personal
details live in user_profiles (one row, created on first save) and the picture in user_avatars; see app/models.py.
Errors are fixed messages naming the field, never exception text.
"""
import io
import re
from datetime import datetime

from flask import Blueprint, Response, current_app, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app import db, usernames
from app.models import User, UserAvatar, UserProfile
from app.routes._util import iso_utc
from app.routes.auth import PASSWORD_RULE_MESSAGE, is_valid_password
from app.security import rate_limit_hit, rate_limited_response

profile_bp = Blueprint("profile", __name__)

# ---------------------------------------------------------------- details
TEXT_LIMITS = {"college": 150, "branch": 100, "city": 80, "bio": 300}
PHONE_RE = re.compile(r"^\+?[0-9][0-9 \-]{5,18}[0-9]$")
URL_HOSTS = {"linkedin_url": ("linkedin.com", "LinkedIn"), "github_url": ("github.com", "GitHub")}
DETAIL_FIELDS = ["phone", "college", "branch", "year_of_study", "graduation_year", "city", "linkedin_url",
                 "github_url", "bio"]
YEAR_OF_STUDY = (1, 5)
GRADUATION_YEARS = (2000, 2040)

# ---------------------------------------------------------------- picture
AVATAR_MAX_BYTES = 4 * 1024 * 1024    # under the app-wide 5 MB MAX_CONTENT_LENGTH
AVATAR_MAX_PIXELS = 25_000_000        # refuse huge images before decoding them (decompression bombs)
AVATAR_SIZE = 256
AVATAR_FORMATS = {"JPEG", "PNG", "WEBP"}
AVATAR_UPLOADS_PER_HOUR = 20
PASSWORD_CHANGES_PER_15_MIN = 10


def _bad(field, message, status=400):
    return jsonify({"error": message, "field": field}), status


def _clean_text(value):
    return value.strip() if isinstance(value, str) else None


def _parse_int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def validate_details(data):
    """(cleaned {field: value or None}, None) or (None, (field, message)). Empty strings become None."""
    out = {}
    for field in DETAIL_FIELDS:
        if field not in data:
            continue
        raw = data[field]
        if raw is None or (isinstance(raw, str) and raw.strip() == ""):
            out[field] = None
            continue
        if field in ("year_of_study", "graduation_year"):
            value = _parse_int(raw)
            low, high = YEAR_OF_STUDY if field == "year_of_study" else GRADUATION_YEARS
            if value is None or not low <= value <= high:
                label = "Year of study" if field == "year_of_study" else "Graduation year"
                return None, (field, f"{label} must be a number from {low} to {high}.")
            out[field] = value
            continue
        value = _clean_text(raw)
        if value is None:
            return None, (field, "That value isn't text.")
        if field == "phone":
            if not PHONE_RE.match(value) or not 7 <= sum(c.isdigit() for c in value) <= 15:
                return None, (field, "Enter a phone number of 7-15 digits (an optional + and spaces or dashes are fine).")
        elif field in URL_HOSTS:
            host, label = URL_HOSTS[field]
            if len(value) > 200 or not re.match(rf"^https?://([a-z0-9-]+\.)*{re.escape(host)}(/|$)", value, re.I):
                return None, (field, f"Enter your full {label} link, starting with https:// and on {host}.")
        elif len(value) > TEXT_LIMITS[field]:
            return None, (field, f"Keep this under {TEXT_LIMITS[field]} characters.")
        out[field] = value
    return out, None


def _avatar_url(user):
    avatar = user.avatar
    if avatar is None:
        return None
    stamp = int((avatar.updated_at or datetime.utcnow()).timestamp())
    return f"/profile/avatar?v={stamp}"


def _profile_dict(user):
    details = user.profile
    return {
        "username": user.username,
        "name": user.name,
        "email": user.email,
        "member_since": iso_utc(user.created_at),
        "avatar_url": _avatar_url(user),
        "details": {f: (getattr(details, f) if details else None) for f in DETAIL_FIELDS},
    }


def _progress_summary(user_id):
    """Level, XP and badges for the profile's side card; None if that part fails (the profile still loads)."""
    try:
        from app.routes.gamification import summary_for
        s = summary_for(user_id)
        return {"level": s["level"], "xp": s["xp"], "badges_earned": s["counts"]["badges_earned"],
                "badges_total": s["counts"]["badges_total"], "scenarios_passed": s["counts"]["scenarios_passed"],
                "codes_solved": s["counts"]["codes_solved"], "streak": s["streak"]}
    except Exception:
        current_app.logger.exception("profile progress summary failed")
        return None


# ---------------------------------------------------------------- routes
@profile_bp.route("/profile/data", methods=["GET"])
@login_required
def get_profile():
    body = _profile_dict(current_user)
    body["progress"] = _progress_summary(current_user.id)
    return jsonify(body), 200


@profile_bp.route("/profile", methods=["POST"])
@login_required
def update_profile():
    """Body: any of name, username and the DETAIL_FIELDS. Only the fields sent are changed."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _bad(None, "Send the profile as JSON.")

    user = current_user
    # Validate everything first, then change anything, so a bad field never leaves a half-applied update.
    name = username = None
    if "name" in data:
        name = _clean_text(data["name"])
        if not name:
            return _bad("name", "Enter your full name.")
        if len(name) > 120:
            return _bad("name", "Keep your name under 120 characters.")
    if "username" in data:
        username = usernames.normalize(data["username"])
        if not usernames.is_valid(username):
            return _bad("username", usernames.USERNAME_RULE_MESSAGE)
        if username != user.username:
            taken = db.session.query(User.query.filter(User.username == username, User.id != user.id).exists()).scalar()
            if taken:
                return _bad("username", "That username is taken. Try another.", 409)
    details, error = validate_details(data)
    if error:
        return _bad(*error)

    if name is not None:
        user.name = name
    if username is not None:
        user.username = username
    if details:
        row = user.profile or UserProfile(user_id=user.id)
        for field, value in details.items():
            setattr(row, field, value)
        db.session.add(row)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _bad("username", "That username was just taken. Try another.", 409)
    return jsonify(_profile_dict(user)), 200


def process_avatar(raw):
    """JPEG bytes of a square AVATAR_SIZE picture made from an uploaded image, or raise ValueError(message)."""
    from PIL import Image, ImageOps

    if len(raw) > AVATAR_MAX_BYTES:
        raise ValueError("That picture is over 4 MB. Choose a smaller one.")
    try:
        img = Image.open(io.BytesIO(raw))
        if img.format not in AVATAR_FORMATS:
            raise ValueError
        width, height = img.size
        if width * height > AVATAR_MAX_PIXELS or width < 1 or height < 1:
            raise ValueError
        img.load()
        img = ImageOps.exif_transpose(img)
    except ValueError:
        raise ValueError("That file isn't a JPEG, PNG or WebP picture.")
    except Exception:
        raise ValueError("That file isn't a JPEG, PNG or WebP picture.")
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        flat = Image.new("RGB", img.size, (255, 255, 255))
        flat.paste(img, mask=img.split()[-1])
        img = flat
    else:
        img = img.convert("RGB")
    img = ImageOps.fit(img, (AVATAR_SIZE, AVATAR_SIZE), method=Image.LANCZOS, centering=(0.5, 0.4))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85, optimize=True)   # a fresh file: no EXIF, GPS or other metadata
    return out.getvalue()


@profile_bp.route("/profile/avatar", methods=["POST"])
@login_required
def upload_avatar():
    allowed, retry_after = rate_limit_hit("avatar_upload", current_user.id, AVATAR_UPLOADS_PER_HOUR, 3600)
    if not allowed:
        return rate_limited_response(retry_after)
    file = request.files.get("avatar")
    if file is None or not file.filename:
        return _bad("avatar", "Choose a picture to upload.")
    try:
        image = process_avatar(file.read(AVATAR_MAX_BYTES + 1))
    except ValueError as e:
        return _bad("avatar", str(e))
    row = current_user.avatar or UserAvatar(user_id=current_user.id)
    row.image = image
    row.mime = "image/jpeg"
    row.updated_at = datetime.utcnow()
    db.session.add(row)
    db.session.commit()
    return jsonify({"avatar_url": _avatar_url(current_user)}), 200


@profile_bp.route("/profile/avatar/delete", methods=["POST"])
@login_required
def delete_avatar():
    UserAvatar.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify({"avatar_url": None}), 200


@profile_bp.route("/profile/avatar", methods=["GET"])
@login_required
def get_avatar():
    row = UserAvatar.query.filter_by(user_id=current_user.id).first()
    if row is None:
        return jsonify({"error": "No profile picture."}), 404
    resp = Response(row.image, mimetype=row.mime)
    # The URL carries ?v=<last change>, so a cached copy is never stale; private because it is per account.
    resp.headers["Cache-Control"] = "private, max-age=86400"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


@profile_bp.route("/profile/password", methods=["POST"])
@login_required
def change_password():
    allowed, retry_after = rate_limit_hit("password_change", current_user.id, PASSWORD_CHANGES_PER_15_MIN, 900)
    if not allowed:
        return rate_limited_response(retry_after)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    current_pw, new_pw = data.get("current_password"), data.get("new_password")
    if not isinstance(current_pw, str) or not isinstance(new_pw, str) or not current_pw or not new_pw:
        return _bad(None, "Enter your current password and a new one.")
    if not current_user.check_password(current_pw):
        return _bad("current_password", "Your current password isn't right.")
    if not is_valid_password(new_pw):
        return _bad("new_password", PASSWORD_RULE_MESSAGE)
    if new_pw == current_pw:
        return _bad("new_password", "The new password must be different from the current one.")
    current_user.set_password(new_pw)
    db.session.commit()
    return jsonify({"message": "Password changed."}), 200
