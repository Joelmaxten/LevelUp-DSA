"""
Send ONE test email with the app's own mail settings and say which stage fails (connect, TLS, login, send) and what the
server answered. Use it to debug the forgot-password email without the web app. Prints no password.

Usage:   PYTHONPATH=. python scripts/test_mail.py you@example.com
Reads MAIL_USERNAME, MAIL_PASSWORD, MAIL_SMTP_HOST, MAIL_SMTP_PORT, MAIL_FROM from .env (same rules as the app).
"""
import smtplib
import ssl
import sys
from email.message import EmailMessage

from dotenv import load_dotenv
load_dotenv(".env")

from app.config import Config  # noqa: E402


def main(to_address):
    user, host, port = Config.MAIL_USERNAME, Config.MAIL_SMTP_HOST, Config.MAIL_SMTP_PORT
    password = Config.MAIL_PASSWORD.replace(" ", "")
    print(f"host={host} port={port} user={user or '(empty)'} password={'set, %d characters' % len(password) if password else '(empty)'}")
    if not user or not password:
        print("MAIL_USERNAME / MAIL_PASSWORD are empty: nothing to test.")
        return 1
    if len(password) != 16:
        print("note: a Google App Password has exactly 16 characters; yours has", len(password))
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = "LevelUp DSA mail test", Config.MAIL_FROM or user, to_address
    msg.set_content("If you can read this, the forgot-password email will work.")
    stage = "connect"
    try:
        context = ssl.create_default_context()
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, context=context, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
        print("connect: OK")
        server.set_debuglevel(0)
        if port != 465:
            stage = "starttls"
            server.starttls(context=context)
            print("starttls: OK")
        stage = "login"
        server.login(user, password)
        print("login: OK")
        stage = "send"
        refused = server.send_message(msg)
        print("send: OK" + (f" (refused: {refused})" if refused else ""))
        server.quit()
        print(f"\nDone. Check the inbox (and spam) of {to_address}.")
        return 0
    except Exception as exc:
        print(f"{stage}: FAILED  {type(exc).__name__}: {str(exc)[:300]}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]) if len(sys.argv) > 1 else print(__doc__) or 2)
