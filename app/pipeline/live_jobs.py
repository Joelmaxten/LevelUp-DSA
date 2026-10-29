"""
All live job listings for a career path in one answer: Adzuna and (when JOOBLE_API_KEY is set) Jooble, asked at the
same time, interleaved, with duplicates removed across both, each listing tagged with its source. Also returns
plain "search on LinkedIn / Naukri / Indeed" links: they open the site's own search page in the student's browser;
nothing is scraped or fetched from those sites.

Never raises. "unavailable" is True only when listings is empty because every source that was asked failed.
"""
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, quote_plus

from flask import current_app

from app.pipeline import adzuna_listings, jooble_listings
from app.pipeline.adzuna_listings import SEARCH_TERMS, dedupe_listings

MAX_SHOWN = 8


def search_links(career_path):
    """The site's own job-search pages for this path's search phrase (fixed hosts, phrase URL-encoded)."""
    term = SEARCH_TERMS[career_path]
    return [
        {"name": "LinkedIn", "url": f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(term)}&location=India"},
        {"name": "Naukri", "url": f"https://www.naukri.com/{quote(term.lower().replace(' ', '-'))}-jobs"},
        {"name": "Indeed", "url": f"https://in.indeed.com/jobs?q={quote_plus(term)}&l=India"},
    ]


def _interleave(lists):
    merged = []
    for position in range(max((len(items) for items in lists), default=0)):
        for items in lists:
            if position < len(items):
                merged.append(items[position])
    return merged


def get_live_job_listings(career_path):
    app = current_app._get_current_object()
    sources = [("Adzuna", adzuna_listings.get_live_listings)]
    if jooble_listings.is_configured():
        sources.append(("Jooble", jooble_listings.get_jooble_listings))

    def ask(source):
        name, fetch = source
        try:
            with app.app_context():
                return name, fetch(career_path)
        except Exception:
            return name, {"listings": [], "unavailable": True}

    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        answers = list(pool.map(ask, sources))

    per_source, working = [], []
    for name, result in answers:
        if not result["unavailable"]:
            working.append(name)
        per_source.append([{**listing, "source": name} for listing in result["listings"]])

    listings = dedupe_listings(_interleave(per_source))[:MAX_SHOWN]
    return {
        "listings": listings,
        "unavailable": not working,
        "sources": working,
        "search_links": search_links(career_path),
    }
