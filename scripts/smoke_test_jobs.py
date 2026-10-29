"""
Smoke test for the live job listings: duplicate removal, the optional Jooble source, the combiner
(app/pipeline/live_jobs.py) and the LinkedIn / Naukri / Indeed search links. Stubs only: no network, no database,
no real keys (the "secrets" are made-up strings). A bare Flask app supplies the config the modules read.

Usage:
    PYTHONPATH=. python scripts/smoke_test_jobs.py
"""
import json
import logging
import sys
from unittest.mock import patch

from flask import Flask

from app.pipeline import adzuna_listings as al
from app.pipeline import jooble_listings as jl
from app.pipeline import live_jobs as lj
from app.pipeline.career_path_registry import CAREER_PATHS

JOOBLE_KEY = "JOOBLE-SECRET-KEY-abc123xyz789"
ADZ_ID, ADZ_KEY = "ADZ_ID_secret_111", "ADZ_KEY_secret_222"
checks = []


def check(description, condition):
    checks.append((description, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {description}")


class Resp:
    def __init__(self, status=200, data=None, bad_json=False):
        self.status_code, self._data, self._bad = status, data, bad_json

    def json(self):
        if self._bad:
            raise ValueError("not json")
        return self._data


def adz(title, company, loc="India", n=1):
    return {"title": title, "company": {"display_name": company}, "location": {"display_name": loc},
            "redirect_url": f"https://adz.test/{title}-{company}-{n}".replace(" ", "-")}


def joo(title, company, link=None, loc="Bengaluru"):
    return {"title": title, "company": company, "location": loc,
            "link": link if link is not None else f"https://jooble.test/{title}-{company}".replace(" ", "-")}


def make_app(jooble=True):
    app = Flask(__name__)
    app.config.update(ADZUNA_APP_ID=ADZ_ID, ADZUNA_APP_KEY=ADZ_KEY, JOOBLE_API_KEY=JOOBLE_KEY if jooble else "")
    return app


def fresh():
    al._cache.clear()
    jl._cache.clear()


class Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


def main():
    # ------------------------------------------------------------ dedupe
    same = [{"title": "Full-Stack Developer", "company": "VSI Infotech LLP"},
            {"title": "Full Stack Developer", "company": "VSI Infotech LLP"},
            {"title": "FULL STACK  DEVELOPER", "company": "vsi infotech llp"},
            {"title": "Full Stack Developer", "company": "VASA Denticity Limited"},
            {"title": "Full Stack Developer", "company": None}]
    kept = al.dedupe_listings(same)
    check("dedupe: hyphen, case and spacing variants of the same title+company collapse to one",
          [k["company"] for k in kept] == ["VSI Infotech LLP", "VASA Denticity Limited", None])
    check("dedupe: the FIRST of the duplicates is kept, order preserved", kept[0] is same[0])
    check("dedupe: empty list and missing fields do not raise", al.dedupe_listings([]) == [] and al.dedupe_listings([{}, {}]) == [{}])

    # ------------------------------------------------------------ Adzuna: asks for more than it shows, dedupes
    app = make_app()
    with app.app_context():
        fresh()
        payload = {"results": [adz("Full-Stack Developer", "VSI Infotech LLP", n=1), adz("Full Stack Developer", "VSI Infotech LLP", n=2),
                               adz("Full Stack Developer", "VSI Infotech LLP", n=3), adz("Full Stack Developer", "VASA Denticity Limited"),
                               adz("Full Stack Developer", "The Future University")]}
        with patch("app.pipeline.adzuna_listings.requests.get", return_value=Resp(200, payload)) as g:
            r = al.get_live_listings("Full-Stack Development")
        titles = [(x["company"]) for x in r["listings"]]
        check("adzuna: the screenshot case (3 repeats of one company) now shows each company once",
              titles == ["VSI Infotech LLP", "VASA Denticity Limited", "The Future University"])
        check("adzuna: asks Adzuna for more results than it shows",
              g.call_args.kwargs["params"]["results_per_page"] == al.FETCH_SIZE and al.FETCH_SIZE > 5)
        fresh()
        many = {"results": [adz(f"Job {i}", f"Co {i}") for i in range(12)]}
        with patch("app.pipeline.adzuna_listings.requests.get", return_value=Resp(200, many)):
            r = al.get_live_listings("Full-Stack Development")
        check("adzuna: still returns at most `limit` (5) distinct listings", len(r["listings"]) == 5)

    # ------------------------------------------------------------ Jooble module
    with make_app(jooble=False).app_context():
        fresh()
        check("jooble: not configured without a key", jl.is_configured() is False)
        with patch("app.pipeline.jooble_listings.requests.post") as post:
            r = jl.get_jooble_listings("DevOps")
        check("jooble: without a key no request is made and the answer is 'unavailable'",
              post.call_count == 0 and r == {"listings": [], "unavailable": True})
    with app.app_context():
        fresh()
        check("jooble: configured when a key is set", jl.is_configured() is True)
        body = {"totalCount": 3, "jobs": [
            joo("Senior <b>DevOps</b> Engineer &amp; SRE", "Acme <b>Cloud</b>"),
            joo("DevOps Engineer", "Acme Cloud", link="https://jooble.test/dup"),       # same title+company after cleaning? different title
            joo("Bad link job", "Zed", link="javascript:alert(1)"),
            joo("", "No title"),
            {"title": "No link", "company": "Q"},
            "not a dict",
        ]}
        log = Capture()
        logging.getLogger().addHandler(log)
        with patch("app.pipeline.jooble_listings.requests.post", return_value=Resp(200, body)) as post:
            r = jl.get_jooble_listings("DevOps")
        logging.getLogger().removeHandler(log)
        call = post.call_args
        check("jooble: POSTs to the Jooble URL with the key, the search phrase and India, with a timeout",
              call.args[0] == jl.JOOBLE_URL + JOOBLE_KEY and call.kwargs["json"] == {"keywords": "devops engineer", "location": "India"}
              and call.kwargs["timeout"] == jl.REQUEST_TIMEOUT_SECONDS)
        check("jooble: HTML tags and entities are removed from title and company",
              r["listings"][0]["title"] == "Senior DevOps Engineer & SRE" and r["listings"][0]["company"] == "Acme Cloud")
        check("jooble: listings with a non-http(s) link, no title or no link are skipped, junk entries ignored",
              [x["title"] for x in r["listings"]] == ["Senior DevOps Engineer & SRE", "DevOps Engineer"] and not r["unavailable"])
        check("jooble: listings have the same shape as Adzuna's (salary None, not predicted)",
              set(r["listings"][0]) == {"title", "company", "location", "url", "salary_estimate", "salary_is_predicted"}
              and r["listings"][0]["salary_estimate"] is None and r["listings"][0]["salary_is_predicted"] is False)
        check("jooble: the key is not in the returned value or in any log line",
              JOOBLE_KEY not in json.dumps(r) and not any(JOOBLE_KEY in l for l in log.lines))
        with patch("app.pipeline.jooble_listings.requests.post", return_value=Resp(200, body)) as post2:
            again = jl.get_jooble_listings("DevOps")
        check("jooble: a second call is served from the cache (no request)", post2.call_count == 0 and again == r)

        failures = [("HTTP 500", Resp(500)), ("bad JSON", Resp(200, bad_json=True)), ("missing 'jobs'", Resp(200, {"nope": 1})),
                    ("'jobs' not a list", Resp(200, {"jobs": "x"})), ("401", Resp(401))]
        for name, resp in failures:
            fresh()
            with patch("app.pipeline.jooble_listings.requests.post", return_value=resp):
                r = jl.get_jooble_listings("DevOps")
            check(f"jooble: {name} -> 'unavailable', no exception", r == {"listings": [], "unavailable": True})
        fresh()
        with patch("app.pipeline.jooble_listings.requests.post", side_effect=TimeoutError(f"timed out calling {JOOBLE_KEY}")):
            try:
                r = jl.get_jooble_listings("DevOps")
                err = None
            except Exception as exc:
                r, err = None, exc
        check("jooble: a timeout is swallowed and nothing leaks", err is None and r == {"listings": [], "unavailable": True} and JOOBLE_KEY not in json.dumps(r))

    # ------------------------------------------------------------ combiner
    def adz_payload(*pairs):
        return {"results": [adz(t, c) for t, c in pairs]}

    with app.app_context():
        fresh()
        a = adz_payload(("Backend Developer", "Acme"), ("Backend Developer II", "Beta"), ("Backend Engineer", "Gamma"))
        j = {"jobs": [joo("Backend Developer", "Acme"), joo("Python Developer", "Delta"), joo("API Engineer", "Echo")]}
        with patch("app.pipeline.adzuna_listings.requests.get", return_value=Resp(200, a)), \
             patch("app.pipeline.jooble_listings.requests.post", return_value=Resp(200, j)):
            r = lj.get_live_job_listings("Backend Engineering")
        names = [(x["source"], x["company"]) for x in r["listings"]]
        print("   order:", names)
        check("combined: Adzuna and Jooble listings alternate (Jooble's duplicate Acme dropped), each tagged with its source",
              names == [("Adzuna", "Acme"), ("Adzuna", "Beta"), ("Jooble", "Delta"), ("Adzuna", "Gamma"), ("Jooble", "Echo")])
        check("combined: the same job on both sources (Backend Developer at Acme) appears once, Adzuna's copy kept",
              sum(1 for x in r["listings"] if x["company"] == "Acme") == 1 and ("Adzuna", "Acme") in names)
        check("combined: both sources worked -> sources lists both, not unavailable",
              r["sources"] == ["Adzuna", "Jooble"] and r["unavailable"] is False)
        check("combined: at most MAX_SHOWN listings", len(r["listings"]) <= lj.MAX_SHOWN)
        check("combined: no key of any kind appears in the result",
              not any(k in json.dumps(r) for k in (JOOBLE_KEY, ADZ_ID, ADZ_KEY)))

        fresh()
        with patch("app.pipeline.adzuna_listings.requests.get", return_value=Resp(500)), \
             patch("app.pipeline.jooble_listings.requests.post", return_value=Resp(200, j)):
            r = lj.get_live_job_listings("Backend Engineering")
        check("combined: Adzuna down, Jooble up -> Jooble's listings are shown, not unavailable, sources == ['Jooble']",
              len(r["listings"]) == 3 and r["unavailable"] is False and r["sources"] == ["Jooble"])
        fresh()
        with patch("app.pipeline.adzuna_listings.requests.get", return_value=Resp(200, a)), \
             patch("app.pipeline.jooble_listings.requests.post", return_value=Resp(500)):
            r = lj.get_live_job_listings("Backend Engineering")
        check("combined: Jooble down, Adzuna up -> Adzuna's listings only, not unavailable",
              len(r["listings"]) == 3 and r["unavailable"] is False and r["sources"] == ["Adzuna"])
        fresh()
        with patch("app.pipeline.adzuna_listings.requests.get", return_value=Resp(500)), \
             patch("app.pipeline.jooble_listings.requests.post", return_value=Resp(500)):
            r = lj.get_live_job_listings("Backend Engineering")
        check("combined: every source down -> unavailable, no listings, search links still present",
              r["unavailable"] is True and r["listings"] == [] and len(r["search_links"]) == 3)
        fresh()
        with patch("app.pipeline.adzuna_listings.requests.get", return_value=Resp(200, {"results": []})), \
             patch("app.pipeline.jooble_listings.requests.post", return_value=Resp(200, {"jobs": []})):
            r = lj.get_live_job_listings("Backend Engineering")
        check("combined: sources answered but found nothing -> empty list, NOT unavailable",
              r["listings"] == [] and r["unavailable"] is False)
        fresh()
        with patch("app.pipeline.adzuna_listings.get_live_listings", side_effect=RuntimeError("boom")), \
             patch("app.pipeline.jooble_listings.get_jooble_listings", return_value={"listings": [], "unavailable": False}):
            try:
                r = lj.get_live_job_listings("Backend Engineering")
                err = None
            except Exception as exc:
                r, err = None, exc
        check("combined: an unexpected crash inside one source is contained (counts as that source being down)",
              err is None and r["sources"] == ["Jooble"])

    with make_app(jooble=False).app_context():
        fresh()
        with patch("app.pipeline.adzuna_listings.requests.get", return_value=Resp(200, adz_payload(("Backend Developer", "Acme")))) as g, \
             patch("app.pipeline.jooble_listings.requests.post") as post:
            r = lj.get_live_job_listings("Backend Engineering")
        check("combined: without a Jooble key only Adzuna is asked (no Jooble request), exactly as before",
              post.call_count == 0 and g.call_count == 1 and r["sources"] == ["Adzuna"] and len(r["listings"]) == 1)

    # ------------------------------------------------------------ search links
    all_ok = True
    for path in CAREER_PATHS:
        links = lj.search_links(path)
        all_ok &= [l["name"] for l in links] == ["LinkedIn", "Naukri", "Indeed"]
        all_ok &= links[0]["url"].startswith("https://www.linkedin.com/jobs/search/?keywords=")
        all_ok &= links[1]["url"].startswith("https://www.naukri.com/") and links[1]["url"].endswith("-jobs")
        all_ok &= links[2]["url"].startswith("https://in.indeed.com/jobs?q=")
        all_ok &= all(" " not in l["url"] and l["url"].startswith("https://") for l in links)
    check("search links: all 15 paths give LinkedIn, Naukri and Indeed links on fixed https hosts with no spaces", all_ok)
    ui = lj.search_links("UI/UX Design")
    check("search links: the phrase is URL-encoded ('UI UX designer' -> no raw slash or space)",
          "keywords=UI+UX+designer" in ui[0]["url"] and "ui-ux-designer-jobs" in ui[1]["url"] and "q=UI+UX+designer" in ui[2]["url"])
    check("search links: nothing is fetched (the module has no HTTP client)", "requests" not in open(lj.__file__, encoding="utf-8").read())

    passed = sum(1 for _, ok in checks if ok)
    print(f"\n{passed}/{len(checks)} checks passed")
    sys.exit(0 if passed == len(checks) else 1)


if __name__ == "__main__":
    main()
