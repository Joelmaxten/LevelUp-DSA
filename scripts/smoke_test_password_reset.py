"""
Smoke test for "forgot password": the emailed single-use link, expiry, rate limits, no account enumeration, and that the
new password works and the old one does not. Uses Flask's test client; the mailer is replaced by a recorder, so no email
is sent and no SMTP server is needed. Deletes every row it created.

Usage:  PYTHONPATH=. python scripts/smoke_test_password_reset.py
"""
import random
import re
import sys
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv(".env")

from app import create_app, db, mailer
from app.models import PasswordResetToken, User
from app.routes import auth
from app.security import reset_rate_limits

OLD, NEW = "OldPass#123", "NewPass#456"
checks = []


def check(description, condition):
    checks.append((description, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {description}")


def main():
    app = create_app()
    app.config["MAIL_ASYNC"] = False
    suffix = random.randint(100000, 999999)
    email = f"resettest{suffix}@example.com"
    sent = []

    def fake_send(config, to, subject, body, debug=False):
        sent.append((to, subject, body))
        return "sent"

    real_send = mailer.send_email
    mailer.send_email = fake_send
    reset_rate_limits()
    try:
        with app.app_context():
            db.create_all()
        with app.test_client() as c:
            html = c.get("/login").get_data(as_text=True)
            check("login page links to /forgot-password", 'href="/forgot-password"' in html)
            check("forgot page renders", c.get("/forgot-password").status_code == 200)
            csrf = re.search(r'<meta name="csrf-token" content="([^"]+)"', html).group(1)
            h = {"X-CSRF-Token": csrf}

            r = c.post("/signup", json={"name": "Reset Test", "email": email, "password": OLD}, headers=h)
            check("test account created", r.status_code == 201)

            check("forgot without CSRF -> 400", c.post("/forgot-password", json={"email": email}).status_code == 400)
            check("bad email -> 400", c.post("/forgot-password", json={"email": "nope"}, headers=h).status_code == 400)
            check("no body -> 400", c.post("/forgot-password", data="x", headers=h).status_code == 400)

            unknown = c.post("/forgot-password", json={"email": f"nobody{suffix}@example.com"}, headers=h)
            known = c.post("/forgot-password", json={"email": email.upper()}, headers=h)
            check("unknown and known email get the same status", unknown.status_code == known.status_code == 200)
            check("unknown and known email get the same message", unknown.get_json() == known.get_json())
            check("exactly one email sent (to the real account)", len(sent) == 1 and sent[0][0] == email)
            body = sent[0][2]
            m = re.search(r"/reset-password\?token=([A-Za-z0-9_-]+)", body)
            check("email holds a reset link", bool(m))
            token = m.group(1)

            with app.app_context():
                row = PasswordResetToken.query.one()
                check("token stored only as a hash", token not in (row.token_hash, ""))
                check("hash is sha256 of the token", row.token_hash == auth._token_hash(token))
                check("expiry about 30 minutes ahead",
                      timedelta(minutes=29) < row.expires_at - datetime.utcnow() < timedelta(minutes=31))

            page = c.get(f"/reset-password?token={token}")
            check("reset page accepts a good token", b'id="reset-form"' in page.data)
            check("reset page sends Referrer-Policy no-referrer", page.headers.get("Referrer-Policy") == "no-referrer")
            check("reset page is not cached", page.headers.get("Cache-Control") == "no-store")
            check("reset page rejects a bad token", b'id="reset-form"' not in c.get("/reset-password?token=abc").data)

            check("weak password -> 400", c.post("/reset-password", json={"token": token, "password": "short"},
                                               headers=h).status_code == 400)
            check("bad token -> 400", c.post("/reset-password", json={"token": "x" * 43, "password": NEW},
                                            headers=h).status_code == 400)
            check("missing token -> 400", c.post("/reset-password", json={"password": NEW}, headers=h).status_code == 400)
            check("weak password did not use up the link",
                  c.post("/reset-password", json={"token": token, "password": "short"}, headers=h).status_code == 400
                  and b'id="reset-form"' in c.get(f"/reset-password?token={token}").data)

            ok = c.post("/reset-password", json={"token": token, "password": NEW}, headers=h)
            check("reset with the good token -> 200", ok.status_code == 200)
            check("link works only once", c.post("/reset-password", json={"token": token, "password": NEW + "x"},
                                                headers=h).status_code == 400)
            check("used link page says invalid", b'id="reset-form"' not in c.get(f"/reset-password?token={token}").data)
            check("old password no longer works",
                  c.post("/login", json={"login": email, "password": OLD}, headers=h).status_code == 401)
            check("new password works",
                  c.post("/login", json={"login": email, "password": NEW}, headers=h).status_code == 200)
            c.post("/logout", headers=h)

            # a newer request replaces the older link
            reset_rate_limits()
            sent.clear()
            c.post("/forgot-password", json={"email": email}, headers=h)
            first = re.search(r"token=([A-Za-z0-9_-]+)", sent[-1][2]).group(1)
            c.post("/forgot-password", json={"email": email}, headers=h)
            second = re.search(r"token=([A-Za-z0-9_-]+)", sent[-1][2]).group(1)
            check("newer link replaces the older one",
                  c.post("/reset-password", json={"token": first, "password": NEW + "!"}, headers=h).status_code == 400
                  and c.get(f"/reset-password?token={second}").data.count(b'id="reset-form"') >= 1)

            # expiry
            with app.app_context():
                PasswordResetToken.query.filter_by(token_hash=auth._token_hash(second)).update(
                    {"expires_at": datetime.utcnow() - timedelta(minutes=1)})
                db.session.commit()
            check("expired link -> 400", c.post("/reset-password", json={"token": second, "password": NEW + "!"},
                                               headers=h).status_code == 400)

            # rate limits: 3 requests per email per hour
            reset_rate_limits()
            codes = [c.post("/forgot-password", json={"email": email}, headers=h).status_code for _ in range(4)]
            check("4th request for one email in an hour -> 429", codes == [200, 200, 200, 429])
            reset_rate_limits()
            codes = [c.post("/forgot-password", json={"email": f"x{i}{suffix}@example.com"}, headers=h).status_code
                     for i in range(11)]
            check("11th request from one address in an hour -> 429", codes[-1] == 429 and set(codes[:-1]) == {200})

        # mailer behaviour without SMTP set up
        cfg = {"MAIL_USERNAME": "", "MAIL_PASSWORD": ""}
        check("no SMTP + debug -> console", real_send(cfg, "a@b.c", "s", "link", debug=True) == "console")
        check("no SMTP + not debug -> failed, link not printed", real_send(cfg, "a@b.c", "s", "link", debug=False) == "failed")
        bad = {"MAIL_USERNAME": "u", "MAIL_PASSWORD": "p", "MAIL_FROM": "", "MAIL_SMTP_HOST": "127.0.0.1",
               "MAIL_SMTP_PORT": 9}
        check("unreachable SMTP -> failed, never raises", real_send(bad, "a@b.c", "s", "b") == "failed")
    finally:
        mailer.send_email = real_send
        with app.app_context():
            user = User.query.filter_by(email=email).first()
            if user:
                PasswordResetToken.query.filter_by(user_id=user.id).delete()
                db.session.delete(user)
                db.session.commit()
            reset_rate_limits()

    failed = [d for d, ok in checks if not ok]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
