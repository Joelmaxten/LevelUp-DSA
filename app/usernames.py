"""
Username rules, shared by signup, the profile page and scripts/add_usernames.py.

A username is 3-20 characters: lowercase letters, numbers and underscores, starting with a letter. It is stored
lowercase, so "Joel_M" and "joel_m" are the same username. It can never contain "@", which is how login tells a
username from an email address.
"""
import re

MIN_LEN, MAX_LEN = 3, 20
USERNAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,19}$")
USERNAME_RULE_MESSAGE = ("Username must be 3-20 characters: lowercase letters, numbers and underscores, "
                         "starting with a letter.")
# Names that would look official or confusing on a profile.
RESERVED = {"admin", "administrator", "root", "support", "help", "system", "levelup", "levelupdsa", "moderator",
            "staff", "null", "none", "undefined", "me", "profile", "login", "signup", "logout"}


def normalize(raw):
    """The username as stored: trimmed and lowercased. Non-strings become ""."""
    return raw.strip().lower() if isinstance(raw, str) else ""


def is_valid(username):
    return bool(USERNAME_RE.match(username)) and username not in RESERVED


def suggest_from_email(email, is_taken):
    """
    A valid, untaken username built from the part of an email before "@" (for accounts made before usernames
    existed, and for API clients that send no username). is_taken(candidate) -> bool. Adds 2, 3, ... until free.
    """
    local = (email or "").split("@")[0].lower()
    base = re.sub(r"[^a-z0-9_]", "_", local)
    base = re.sub(r"_+", "_", base).strip("_")
    if not base or not base[0].isalpha():
        base = "user_" + base if base else "user"
    base = base[:MAX_LEN]
    if len(base) < MIN_LEN:
        base = (base + "_user")[:MAX_LEN]
    candidate, n = base, 1
    while not is_valid(candidate) or is_taken(candidate):
        n += 1
        suffix = str(n)
        candidate = base[:MAX_LEN - len(suffix)] + suffix
    return candidate
