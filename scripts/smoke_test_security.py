"""
Smoke test for the security hardening: CSRF protection, session-cookie flags,
production SECRET_KEY check, the roadmap daily cap and the resume rate limits.
Uses Flask's test client (no browser); no Gemini/YouTube/Adzuna call is made -
every request below is rejected before reaching one.

Usage:
    PYTHONPATH=. python scripts/smoke_test_security.py

Deletes every row it created. Exits non-zero if any check fails.
"""
import io
import os
import random
import re
import sys
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv()

from app import create_app, db
from app.models import GeneratedRoadmap, User
from app.security import reset_rate_limits

PASSWORD = "SmokeTest#123"
checks = []


def check(description, condition):
    checks.append((description, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {description}")


def token_from(client):
    html = client.get("/").get_data(as_text=True)
    return re.search(r'<meta name="csrf-token" content="([^"]+)"', html).group(1)


def is_csrf_error(resp):
    return resp.status_code == 400 and resp.get_json() == {"error": "csrf"}


def txt_upload():
    return {"resume": (io.BytesIO(b"x"), "notes.txt")}


def main():
    app = create_app()  # plain test client on purpose: tokens are handled by hand here
    suffix = random.randint(100000, 999999)
    email = f"sectest{suffix}@example.com"
    user_id = None

    try:
        with app.app_context():
            db.create_all()

        with app.test_client() as client:
            token = token_from(client)
            check("layout renders a csrf-token meta tag", len(token) >= 32)
            check("token is stable within a session", token_from(client) == token)

            # Three representative routes: signup (public), login (public), quiz start (authed).
            signup_body = {"name": "Sec Test", "email": email, "password": PASSWORD}
            check("signup without token -> 400 csrf", is_csrf_error(client.post("/signup", json=signup_body)))
            check("signup with wrong token -> 400 csrf",
                  is_csrf_error(client.post("/signup", json=signup_body, headers={"X-CSRF-Token": "nope"})))
            good = {"X-CSRF-Token": token}
            resp = client.post("/signup", json=signup_body, headers=good)
            check("signup with valid token -> 201", resp.status_code == 201)
            user_id = (resp.get_json() or {}).get("user_id")

            check("login without token -> 400 csrf",
                  is_csrf_error(client.post("/login", json={"email": email, "password": PASSWORD})))
            resp = client.post("/login", json={"email": email, "password": PASSWORD}, headers=good)
            check("login with valid token -> 200", resp.status_code == 200)

            cookies = resp.headers.getlist("Set-Cookie")
            session_cookie = next((c for c in cookies if c.startswith("session=")), "")
            check("session cookie is HttpOnly", "HttpOnly" in session_cookie)
            check("session cookie is SameSite=Lax", "SameSite=Lax" in session_cookie)
            check("session cookie is not Secure in development", "Secure" not in session_cookie)

            check("quiz/start without token -> 400 csrf", is_csrf_error(client.post("/quiz/start")))
            check("quiz/start with wrong token -> 400 csrf",
                  is_csrf_error(client.post("/quiz/start", headers={"X-CSRF-Token": token[::-1]})))
            check("quiz/start with valid token -> 200", client.post("/quiz/start", headers=good).status_code == 200)

            check("GET routes need no token", client.get("/dashboard/data").status_code == 200
                  and client.get("/career/options").status_code == 200)

            # Multipart upload: header-borne token works; a missing token is refused before the file is read.
            check("multipart upload without token -> 400 csrf",
                  is_csrf_error(client.post("/resume/upload", data=txt_upload(), content_type="multipart/form-data")))
            resp = client.post("/resume/upload", data=txt_upload(), content_type="multipart/form-data", headers=good)
            check("multipart upload with valid token reaches the route (400 'only PDF')",
                  resp.status_code == 400 and "PDF" in resp.get_json()["error"])
            check("error responses carry no 'detail' key", "detail" not in (resp.get_json() or {}))

            # Roadmap daily cap: fill the window directly, no generation.
            with app.app_context():
                limit = app.config["ROADMAP_DAILY_LIMIT"]
                for i in range(limit):
                    db.session.add(GeneratedRoadmap(
                        user_id=user_id, career_path="Backend Engineering", steps={"phases": []},
                        created_at=datetime.utcnow() - timedelta(hours=23, minutes=59 - i)))
                db.session.commit()
            resp = client.post("/roadmap/generate", json={"target_career_path": "Backend Engineering"}, headers=good)
            body = resp.get_json() or {}
            check("roadmap generate over the daily cap -> 429 daily_limit",
                  resp.status_code == 429 and body.get("error") == "daily_limit" and body.get("limit") == limit)
            check("resets_in_minutes reflects the oldest roadmap (1..60)", 1 <= body.get("resets_in_minutes", 0) <= 60)

            with app.app_context():  # age the rows out of the window -> the cap lifts
                GeneratedRoadmap.query.filter_by(user_id=user_id).update(
                    {"created_at": datetime.utcnow() - timedelta(hours=25)})
                db.session.commit()
            resp = client.post("/roadmap/generate", json={"target_career_path": "Not A Path"}, headers=good)
            check("cap lifts once roadmaps are older than 24h (request reaches validation: 400)",
                  resp.status_code == 400 and resp.get_json().get("error") == "invalid_career_path")

            # Resume rate limits (in-process counters).
            app.config["RESUME_UPLOAD_LIMIT_PER_HOUR"] = 2
            app.config["RESUME_LISTINGS_LIMIT_PER_HOUR"] = 2
            reset_rate_limits()
            codes = [client.post("/resume/upload", data=txt_upload(), content_type="multipart/form-data",
                                 headers=good).status_code for _ in range(3)]
            check("resume upload: 3rd request within the limit window -> 429", codes == [400, 400, 429])
            codes = [client.get("/resume/listings?career_path=Nope").status_code for _ in range(3)]
            check("resume listings: 3rd request within the limit window -> 429", codes == [400, 400, 429])
            reset_rate_limits()

        # Production mode.
        saved = {k: os.environ.get(k) for k in ("SECRET_KEY", "SESSION_COOKIE_SECURE")}
        try:
            os.environ.pop("SESSION_COOKIE_SECURE", None)
            for label, bad in (("unset", None), ("empty", ""), ("dev default", "dev-secret-key-change-me"),
                               ("example placeholder", "change-me-to-a-random-string"), ("too short", "short")):
                if bad is None:
                    os.environ.pop("SECRET_KEY", None)
                else:
                    os.environ["SECRET_KEY"] = bad
                try:
                    create_app("production")
                    refused = False
                except RuntimeError:
                    refused = True
                check(f"production refuses to start with SECRET_KEY {label}", refused)
            os.environ["SECRET_KEY"] = "x" * 40
            prod = create_app("production")
            check("production starts with a real SECRET_KEY", True)
            check("production session cookie is Secure by default", prod.config["SESSION_COOKIE_SECURE"] is True)
            check("production keeps HttpOnly + SameSite=Lax",
                  prod.config["SESSION_COOKIE_HTTPONLY"] and prod.config["SESSION_COOKIE_SAMESITE"] == "Lax")
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
    finally:
        with app.app_context():
            if user_id:
                GeneratedRoadmap.query.filter_by(user_id=user_id).delete()
            User.query.filter_by(email=email).delete()
            db.session.commit()

    passed = sum(1 for _, ok in checks if ok)
    print(f"\n{passed}/{len(checks)} checks passed")
    sys.exit(0 if passed == len(checks) else 1)


if __name__ == "__main__":
    main()
