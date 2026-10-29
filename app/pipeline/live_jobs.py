"""
All live job listings for a career path in one answer: Adzuna and (when JOOBLE_API_KEY is set) Jooble, asked at the
same time, interleaved, with duplicates removed across both, each listing tagged with its source. Also returns
plain "search on LinkedIn / Naukri / Indeed" links (entry-level and internship): they open the site's own search page in the student's browser;
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
    """Each site's own search page, once for entry-level jobs and once for internships (fixed hosts, phrase
    URL-encoded). The filter parameters (LinkedIn f_E: 1 = internship, 2 = entry level; Naukri experience=0;
    "fresher"/"intern" in the phrase) come from how those sites' URLs are commonly built and could not be
    tested from the server, so a site may ignore one: the page still opens a normal search."""
    term = SEARCH_TERMS[career_path]
    fresher, intern = f"{term} fresher", f"{term} intern"
    return [
        {"name": "LinkedIn", "kind": "fresher",
         "url": f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(term)}&location=India&f_E=1%2C2"},
        {"name": "Naukri", "kind": "fresher",
         "url": f"https://www.naukri.com/{quote(term.lower().replace(' ', '-'))}-jobs?experience=0"},
        {"name": "Indeed", "kind": "fresher",
         "url": f"https://in.indeed.com/jobs?q={quote_plus(fresher)}&l=India"},
        {"name": "LinkedIn", "kind": "internship",
         "url": f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(intern)}&location=India&f_E=1"},
        {"name": "Naukri", "kind": "internship",
         "url": f"https://www.naukri.com/{quote(intern.lower().replace(' ', '-'))}-jobs"},
        {"name": "Indeed", "kind": "internship",
         "url": f"https://in.indeed.com/jobs?q={quote_plus(intern)}&l=India"},
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
