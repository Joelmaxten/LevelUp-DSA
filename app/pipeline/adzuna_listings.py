"""
Live job listings from the Adzuna API for a career path - a runtime call,
never stored (this was the master doc's original design intent for "Live
Jobs"; no Adzuna-calling code existed anywhere before this module - see
the read-only resume-salary investigation that preceded this task).
Deliberately separate from /resume/upload and /resume/latest (same
reasoning as youtube_resources.py being its own endpoint): a flaky
external call must never block or slow down the resume analysis a
student already has - see GET /resume/listings in routes/resume.py.

Never raises: any HTTP error, timeout, non-200 status, malformed JSON, or
missing expected key in Adzuna's response is treated as "unavailable",
same graceful-degradation contract as fetch_video_for_step /
fetch_resources_for_roadmap.
"""

import time

import requests
from flask import current_app

from app.pipeline.career_path_registry import CAREER_PATHS

ADZUNA_SEARCH_URL = "https://api.adzuna.com/v1/api/jobs/in/search/1"
REQUEST_TIMEOUT_SECONDS = 5
CACHE_TTL_SECONDS = 6 * 60 * 60
FAILURE_CACHE_TTL_SECONDS = 60

# One natural job-title search phrase per career path - there was no
# existing path->job-title mapping to reuse (india_jobs_processor.py's
# CAREER_PATH_KEYWORDS goes the other direction - title->path - and is
# keyed by the old 10 path names, out of scope). Keys read from
# CAREER_PATHS itself (not retyped), asserted complete below.
SEARCH_TERMS = {
    "Full-Stack Development": "full stack developer",
    "AI Engineering": "AI engineer",
    "Machine Learning Engineering": "machine learning engineer",
    "Data Science": "data scientist",
    "Data Analytics": "data analyst",
    "Cybersecurity": "cybersecurity analyst",
    "Mobile App Development": "mobile app developer",
    "Game Development": "game developer",
    "Backend Engineering": "backend developer",
    "UI/UX Design": "UI UX designer",
    "Frontend Development": "frontend developer",
    "Cloud Engineering": "cloud engineer",
    "DevOps": "devops engineer",
    "QA & Test Automation": "QA automation engineer",
    "Data Engineering": "data engineer",
}

assert set(SEARCH_TERMS) == set(CAREER_PATHS), (
    f"SEARCH_TERMS must cover exactly CAREER_PATHS - "
    f"missing: {set(CAREER_PATHS) - set(SEARCH_TERMS)}, "
    f"extra (stale/unknown path names): {set(SEARCH_TERMS) - set(CAREER_PATHS)}"
)

# {search_term: (expires_at, result_dict)} - module-level, same pattern as
# routes/roadmap.py's _index_cache. A successful result is cached for
# CACHE_TTL_SECONDS; an unavailable one only for FAILURE_CACHE_TTL_SECONDS,
# so a transient Adzuna outage doesn't poison the cache for hours.
_cache = {}


def _unavailable():
    return {"listings": [], "unavailable": True}


def _cache_get(term):
    entry = _cache.get(term)
    if entry is None:
        return None
    expires_at, result = entry
    if time.monotonic() >= expires_at:
        return None
    return result


def _cache_set(term, result, ttl_seconds):
    _cache[term] = (time.monotonic() + ttl_seconds, result)
    return result


def _normalize_listing(raw):
    """
    Raises (KeyError/TypeError) if `raw` is missing a required field -
    caught by get_live_listings, which treats that as "unavailable" for
    the whole response rather than silently dropping one bad listing.
    """
    salary_min = raw.get("salary_min")
    salary_max = raw.get("salary_max")
    salary_estimate = (salary_min + salary_max) / 2 if salary_min is not None and salary_max is not None else None

    return {
        "title": raw["title"],
        "company": (raw.get("company") or {}).get("display_name"),
        "location": (raw.get("location") or {}).get("display_name"),
        "url": raw["redirect_url"],
        "salary_estimate": salary_estimate,
        # Adzuna documents this as a string "0"/"1", not a real boolean.
        "salary_is_predicted": str(raw.get("salary_is_predicted", "0")) == "1",
    }


def get_live_listings(career_path, limit=5):
    """
    {"listings": [...], "unavailable": bool} for this career path - never
    raises. "unavailable" (listings always []) covers any failure: a
    non-200 status, a timeout, a connection error, malformed JSON, or a
    response missing an expected key. An empty-but-successful result
    ({"listings": [], "unavailable": False}) is a distinct "no listings
    found" state the caller (GET /resume/listings) and the frontend both
    treat differently from "unavailable".

    The Adzuna app_id/app_key are read from Flask config, used only as
    request parameters - never included in the return value, a log line,
    or an exception message, so they can't leak via this function's
    output under any failure path.
    """
    term = SEARCH_TERMS[career_path]

    cached = _cache_get(term)
    if cached is not None:
        return cached

    params = {
        "app_id": current_app.config["ADZUNA_APP_ID"],
        "app_key": current_app.config["ADZUNA_APP_KEY"],
        "results_per_page": limit,
        "what": term,
        "content-type": "application/json",
    }

    try:
        response = requests.get(ADZUNA_SEARCH_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        if response.status_code != 200:
            return _cache_set(term, _unavailable(), FAILURE_CACHE_TTL_SECONDS)
        data = response.json()
        listings = [_normalize_listing(r) for r in data["results"][:limit]]
    except Exception:
        return _cache_set(term, _unavailable(), FAILURE_CACHE_TTL_SECONDS)

    return _cache_set(term, {"listings": listings, "unavailable": False}, CACHE_TTL_SECONDS)
