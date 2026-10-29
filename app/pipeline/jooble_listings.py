"""
Live job listings from the Jooble API for a career path: an optional second source next to Adzuna.

Same contract as adzuna_listings.get_live_listings: a runtime call, never stored, never raises, results
cached for a few hours (failures only for a minute). Without JOOBLE_API_KEY it is simply not used
(is_configured() is False and nothing is requested).

The key is part of the request URL (that is how Jooble's REST API works), so it is only ever used to build
the request: it never appears in a return value, a log line or an exception message.

NOT VERIFIED against the real service: Jooble's documentation sits behind a sign-up form, so the request
and response shapes below (POST https://jooble.org/api/<key> with {"keywords", "location"}, replying
{"jobs": [{"title", "company", "location", "link", ...}]}) are written from the commonly published form and
tested only with stubs. Any other shape is treated as "unavailable", never as a crash.
"""
import html
import re
import time

import requests
from flask import current_app

from app.pipeline.adzuna_listings import SEARCH_TERMS, dedupe_listings

JOOBLE_URL = "https://jooble.org/api/"
REQUEST_TIMEOUT_SECONDS = 5
CACHE_TTL_SECONDS = 6 * 60 * 60
FAILURE_CACHE_TTL_SECONDS = 60
LOCATION = "India"

_cache = {}
_TAG = re.compile(r"<[^>]+>")


def is_configured():
    return bool(current_app.config.get("JOOBLE_API_KEY"))


def _unavailable():
    return {"listings": [], "unavailable": True}


def _cache_get(term):
    entry = _cache.get(term)
    if entry is None or time.monotonic() >= entry[0]:
        return None
    return entry[1]


def _cache_set(term, result, ttl_seconds):
    _cache[term] = (time.monotonic() + ttl_seconds, result)
    return result


def _text(value):
    """Plain text: Jooble wraps matched words in <b> tags and escapes entities."""
    if not isinstance(value, str):
        return None
    cleaned = html.unescape(_TAG.sub("", value)).strip()
    return cleaned or None


def _normalize_listing(raw):
    """The listing in the app's shape, or None when it has no usable title or link (skipped, not fatal)."""
    title, link = _text(raw.get("title")), raw.get("link")
    if not title or not isinstance(link, str) or not link.lower().startswith(("https://", "http://")):
        return None
    return {
        "title": title,
        "company": _text(raw.get("company")),
        "location": _text(raw.get("location")),
        "url": link,
        # Jooble's salary is free text ("₹5L - 8L a year"), so it is not parsed into a number.
        "salary_estimate": None,
        "salary_is_predicted": False,
    }


def get_jooble_listings(career_path, limit=5):
    """{"listings": [...], "unavailable": bool}; never raises. Call only when is_configured()."""
    term = SEARCH_TERMS[career_path]
    cached = _cache_get(term)
    if cached is not None:
        return cached
    key = current_app.config.get("JOOBLE_API_KEY", "")
    if not key:
        return _unavailable()
    try:
        response = requests.post(JOOBLE_URL + key, json={"keywords": term, "location": LOCATION},
                                 timeout=REQUEST_TIMEOUT_SECONDS)
        if response.status_code != 200:
            return _cache_set(term, _unavailable(), FAILURE_CACHE_TTL_SECONDS)
        jobs = response.json()["jobs"]
        if not isinstance(jobs, list):
            return _cache_set(term, _unavailable(), FAILURE_CACHE_TTL_SECONDS)
        normalized = [n for n in (_normalize_listing(j) for j in jobs if isinstance(j, dict)) if n]
    except Exception:
        return _cache_set(term, _unavailable(), FAILURE_CACHE_TTL_SECONDS)
    return _cache_set(term, {"listings": dedupe_listings(normalized)[:limit], "unavailable": False}, CACHE_TTL_SECONDS)
