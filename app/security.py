"""
Request-level security: CSRF protection and small in-process rate limits.

CSRF: a random token is stored in the session (so it is bound to the browser's
session cookie) and rendered into layout.html as <meta name="csrf-token">. The
shared fetch helpers in static/js/ui.js send it back as the X-CSRF-Token
header on every POST/PUT/PATCH/DELETE. GET/HEAD/OPTIONS are never checked, so
they must stay free of side effects.

Rate limits are per-process counters (a dict of timestamps), which is enough
for a single-worker deployment. With several workers each keeps its own count,
so the effective limit is multiplied - move to a shared store (Redis) if the
app is ever run that way.
"""
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque

from flask import jsonify, request, session

CSRF_SESSION_KEY = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def get_csrf_token():
    """The session's CSRF token, created on first use."""
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def _csrf_guard():
    if request.method in SAFE_METHODS:
        return None
    expected = session.get(CSRF_SESSION_KEY)
    supplied = request.headers.get(CSRF_HEADER, "")
    if not expected or not supplied or not hmac.compare_digest(expected, supplied):
        return jsonify({"error": "csrf"}), 400
    return None


def init_security(app):
    app.before_request(_csrf_guard)

    @app.context_processor
    def inject_csrf_token():
        return {"csrf_token": get_csrf_token}


_hits = defaultdict(deque)
_hits_lock = threading.Lock()


def rate_limit_hit(bucket, key, limit, window_seconds):
    """
    Record one hit for (bucket, key) and report whether it is allowed.
    Returns (True, 0) if within `limit` hits per `window_seconds`, else
    (False, seconds_until_the_oldest_hit_expires). A rejected hit is not recorded.
    """
    now = time.monotonic()
    with _hits_lock:
        q = _hits[(bucket, key)]
        while q and now - q[0] >= window_seconds:
            q.popleft()
        if len(q) >= limit:
            return False, int(window_seconds - (now - q[0])) + 1
        q.append(now)
        return True, 0


def reset_rate_limits():
    """For tests."""
    with _hits_lock:
        _hits.clear()


def rate_limited_response(retry_after_seconds):
    resp = jsonify({"error": "rate_limited",
                    "message": "You're doing that too often. Please wait a bit and try again.",
                    "retry_after_seconds": retry_after_seconds})
    resp.status_code = 429
    resp.headers["Retry-After"] = str(retry_after_seconds)
    return resp
