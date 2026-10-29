"""
Minimal email sending for the password-reset link, standard library only (smtplib), so no extra package.

send_email returns "sent", "console" (SMTP not configured, development only: the message is printed in the server
terminal) or "failed". It never raises and never logs the password or the full message body outside the console case.
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
    try:
        port = config["MAIL_SMTP_PORT"]
        context = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(config["MAIL_SMTP_HOST"], port, context=context, timeout=15) as server:
                server.login(config["MAIL_USERNAME"], config["MAIL_PASSWORD"])
                server.send_message(msg)
        else:
            with smtplib.SMTP(config["MAIL_SMTP_HOST"], port, timeout=15) as server:
                server.starttls(context=context)
                server.login(config["MAIL_USERNAME"], config["MAIL_PASSWORD"])
                server.send_message(msg)
        return "sent"
    except Exception as exc:   # SMTPAuthenticationError, timeouts, DNS: the caller treats them all as "not sent"
        log.warning("email_failed to=%s kind=%s", to_address, type(exc).__name__)
        return "failed"
