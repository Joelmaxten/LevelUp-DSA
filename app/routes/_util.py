from flask import jsonify, request

from app.pipeline.career_quiz_data import CAREER_PATHS


def iso_utc(dt):
    """
    ISO-8601 string for a model timestamp. The created_at / uploaded_at columns
    default to datetime.utcnow() (naive UTC), so append "Z" to make that explicit -
    otherwise browsers would parse the value as local time.
    """
    return dt.isoformat() + "Z" if dt else None


def _requested_career_path():
    """
    The optional "target_career_path" the client sent: a multipart/form field
    (resume upload), a key in a JSON body (roadmap generate), or a query-string
    parameter (GET routes such as the DSA map). None if absent or empty;
    otherwise whatever was sent, unvalidated.
    """
    value = request.form.get("target_career_path")
    if value is None:
        body = request.get_json(silent=True)
        value = body.get("target_career_path") if isinstance(body, dict) else None
    if value is None:
        value = request.args.get("target_career_path")
    return None if value == "" else value


def resolve_target_career_path(profile):
    """
    Which career path a standalone feature (resume analysis, roadmap) should target.
    Returns (career_path, None) on success or (None, error_response) - the caller
    returns error_response as-is.

    - The user has a CareerProfile: their top-ranked path, always. Any
      target_career_path in the request is ignored, so a quiz result is never
      silently overridden.
    - No CareerProfile: the request's target_career_path, which must be an
      EXACT member of CAREER_PATHS - FAISS filtering and the SO Survey lookups
      downstream both match on the exact string, so an arbitrary one would
      silently return nothing. Missing -> 400 "career_path_required" so the
      frontend knows to show a picker; not a valid path -> 400 "invalid_career_path".

    A picked path is a one-off, per-request choice. This function only reads:
    it never creates or updates a CareerProfile, which is the quiz's ranked
    output and only the quiz may write it.
    """
    if profile is not None:
        return profile.career_ranking[0]["career_path"], None

    requested = _requested_career_path()
    if requested is None:
        return None, (jsonify({
            "error": "career_path_required",
            "message": "Choose the career path you're targeting.",
            "options": list(CAREER_PATHS),
        }), 400)

    if not isinstance(requested, str) or requested not in CAREER_PATHS:
        return None, (jsonify({
            "error": "invalid_career_path",
            "message": "That isn't one of the available career paths. Choose one from the list.",
            "options": list(CAREER_PATHS),
        }), 400)

    return requested, None
