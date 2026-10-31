"""
Minimal email sending for the password-reset link, standard library only (smtplib), so no extra package.

send_email returns "sent", "console" (SMTP not configured, development only: the message is printed in the server
terminal) or "failed". It never raises and never logs the password or the message body outside the console case (a failure logs the stage and the server's reply).
"""
import logging
import smtplib
import ssl
from email.message import EmailMessage

log = logging.getLogger(__name__)


def is_configured(config):
    return bool(config.get("MAIL_USERNAME") and config.get("MAIL_PASSWORD"))


def send_email(config, to_address, subject, body, debug=False):
    if not is_configured(config):
        if debug:
            # Development convenience: no SMTP set up, so show the message (it holds the reset link) in the terminal.
            log.warning("email_not_sent (SMTP not configured) to=%s subject=%s\n%s", to_address, subject, body)
            return "console"
        log.warning("email_not_sent: MAIL_USERNAME / MAIL_PASSWORD are not set (to=%s)", to_address)
        return "failed"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config.get("MAIL_FROM") or config["MAIL_USERNAME"]
    msg["To"] = to_address
    msg.set_content(body)
    stage = "connect"
    try:
        host, port = config["MAIL_SMTP_HOST"] or "smtp.gmail.com", config["MAIL_SMTP_PORT"]
        # Google shows an App Password in four groups with spaces; the spaces are not part of it.
        password = config["MAIL_PASSWORD"].replace(" ", "")
        context = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=context, timeout=15) as server:
                stage = "login"
                server.login(config["MAIL_USERNAME"], password)
                stage = "send"
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                stage = "starttls"
                server.starttls(context=context)
                stage = "login"
                server.login(config["MAIL_USERNAME"], password)
                stage = "send"
                server.send_message(msg)
        return "sent"
    except Exception as exc:   # SMTPAuthenticationError, timeouts, DNS: the caller treats them all as "not sent"
        # The exception text is the server's own reply (never the password), and it is what tells the causes apart.
        log.warning("email_failed to=%s stage=%s kind=%s detail=%s", to_address, stage, type(exc).__name__,
                    str(exc)[:200].replace("\n", " "))
        return "failed"
