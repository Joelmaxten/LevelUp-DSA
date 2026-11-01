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
            joo("Junior <b>DevOps</b> Engineer &amp; SRE", "Acme <b>Cloud</b>"),
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
              call.args[0] == jl.JOOBLE_URL + JOOBLE_KEY and call.kwargs["json"] == {"keywords": "devops engineer fresher", "location": "India"}
              and call.kwargs["timeout"] == jl.REQUEST_TIMEOUT_SECONDS)
        check("jooble: HTML tags and entities are removed from title and company",
              r["listings"][0]["title"] == "Junior DevOps Engineer & SRE" and r["listings"][0]["company"] == "Acme Cloud")
        check("jooble: listings with a non-http(s) link, no title or no link are skipped, junk entries ignored",
              [x["title"] for x in r["listings"]] == ["Junior DevOps Engineer & SRE", "DevOps Engineer"] and not r["unavailable"])
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

    # ------------------------------------------------------------ entry-level filter and fresher search
    titles = {"Senior Python Developer": True, "Sr. Data Analyst": True, "Lead DevOps Engineer": True, "Engineering Manager": True,
              "Solutions Architect": True, "Head of Data": True, "Data Analyst (5+ years)": True, "Python Developer - 3 years exp": True,
              "Principal Engineer": True, "Python Developer": False, "Junior Python Developer": False, "Fresher - Data Analyst": False,
              "Software Engineer II": False, "Graduate Trainee Engineer": False, "Intern - Backend": False,
              "Leadership Trainee": False, "Misleading Developer": False}
    wrong = [t for t, senior in titles.items() if al.is_senior({"title": t}) != senior]
    check("filter: senior / lead / manager / architect / head / principal titles and 'N years' are caught, entry-level titles pass", not wrong)
    if wrong:
        print("   wrong:", wrong)
    check("filter: a listing with no title does not raise and is kept", al.entry_level_only([{"title": None}, {}]) == [{"title": None}, {}])

    with app.app_context():
        fresh()
        first = {"results": [adz("Senior Python Developer", "A"), adz("Python Developer", "B"), adz("Lead Python Engineer", "C"), adz("Junior Python Developer", "D")]}
        with patch("app.pipeline.adzuna_listings.requests.get", return_value=Resp(200, first)) as g:
            r = al.get_live_listings("Backend Engineering")
        check("adzuna: senior titles that slip through are dropped from what is shown", [x["company"] for x in r["listings"]] == ["B", "D"])
        p = g.call_args_list[0].kwargs["params"]
        check("adzuna: first request asks for entry-level roles (what_or) and excludes senior words (what_exclude)",
              p["what"] == "backend developer" and p["what_or"] == al.ENTRY_WORDS and p["what_exclude"] == al.EXCLUDE_WORDS and g.call_count == 1)

        fresh()
        calls = []

        def seq(url, params=None, timeout=None):
            calls.append(dict(params))
            return Resp(200, {"results": []}) if "what_or" in params else Resp(200, {"results": [adz("Backend Developer", "Plain Co")]})
        with patch("app.pipeline.adzuna_listings.requests.get", side_effect=seq):
            r = al.get_live_listings("Backend Engineering")
        check("adzuna: when the entry-level search finds nothing, ONE plain search follows and its (filtered) results are used",
              len(calls) == 2 and "what_or" not in calls[1] and [x["company"] for x in r["listings"]] == ["Plain Co"])
        fresh()
        calls.clear()

        def rejected(url, params=None, timeout=None):
            calls.append(dict(params))
            return Resp(400) if "what_or" in params else Resp(200, {"results": [adz("Backend Developer", "Plain Co")]})
        with patch("app.pipeline.adzuna_listings.requests.get", side_effect=rejected):
            r = al.get_live_listings("Backend Engineering")
        check("adzuna: if Adzuna rejects the entry-level parameters (400) the plain search still gives listings, not 'unavailable'",
              len(calls) == 2 and r["unavailable"] is False and len(r["listings"]) == 1)
        fresh()
        with patch("app.pipeline.adzuna_listings.requests.get", return_value=Resp(500)) as g:
            r = al.get_live_listings("Backend Engineering")
        check("adzuna: a server error (500) is not retried and is 'unavailable'", g.call_count == 1 and r == {"listings": [], "unavailable": True})

    with app.app_context():
        fresh()
        seen = []

        def jseq(url, json=None, timeout=None):
            seen.append(json["keywords"])
            return Resp(200, {"jobs": []}) if json["keywords"].endswith("fresher") else Resp(200, {"jobs": [joo("Senior SRE", "S"), joo("DevOps Engineer", "T")]})
        with patch("app.pipeline.jooble_listings.requests.post", side_effect=jseq):
            r = jl.get_jooble_listings("DevOps")
        check("jooble: when '<role> fresher' finds nothing the plain phrase is tried once, and senior titles are still dropped",
              seen == ["devops engineer fresher", "devops engineer"] and [x["company"] for x in r["listings"]] == ["T"])

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
              r["unavailable"] is True and r["listings"] == [] and len(r["search_links"]) == 6)
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

    # ------------------------------------------------------------ verified skills in the search
    check("search skill terms: at most two, a '(AWS)'-style note dropped, case-insensitive duplicates removed, junk skipped",
          al.search_skill_terms(["Python", "SQL", "Docker"]) == ["Python", "SQL"]
          and al.search_skill_terms(["Amazon Web Services (AWS)", "amazon web services"]) == ["Amazon Web Services"]
          and al.search_skill_terms(["", None, "x" * 40, "Git"]) == ["Git"] and al.search_skill_terms(None) == [])

    with app.app_context():
        fresh()
        what = []

        def with_skills(url, params=None, timeout=None):
            what.append(params["what"])
            return Resp(200, adz_payload(("Backend Developer", "Skill Co")))
        with patch("app.pipeline.adzuna_listings.requests.get", side_effect=with_skills):
            r = al.get_live_listings("Backend Engineering", skills=["Python", "SQL", "Docker"])
        check("adzuna: with skills the search phrase gets the first two added ('backend developer Python SQL') and matched_on says so",
              what == ["backend developer Python SQL"] and r["matched_on"] == ["Python", "SQL"] and len(r["listings"]) == 1)

        fresh()
        what.clear()

        def only_plain(url, params=None, timeout=None):
            what.append(params["what"])
            return Resp(200, {"results": []}) if params["what"].endswith("Python SQL") else Resp(200, adz_payload(("Backend Developer", "Plain Co")))
        with patch("app.pipeline.adzuna_listings.requests.get", side_effect=only_plain):
            r = al.get_live_listings("Backend Engineering", skills=["Python", "SQL"])
        check("adzuna: if the skills search returns nothing it falls back to today's plain search, and matched_on is absent",
              what[-1] == "backend developer" and [x["company"] for x in r["listings"]] == ["Plain Co"] and "matched_on" not in r)

        fresh()
        what.clear()
        with patch("app.pipeline.adzuna_listings.requests.get", side_effect=with_skills):
            r = al.get_live_listings("Backend Engineering")
            r2 = al.get_live_listings("Backend Engineering", skills=[])
        check("adzuna: without skills nothing changes (phrase 'backend developer', no matched_on), and the plain result is cached",
              what == ["backend developer"] and "matched_on" not in r and r2 == r)

        fresh()
        what.clear()
        with patch("app.pipeline.adzuna_listings.requests.get", side_effect=with_skills):
            al.get_live_listings("Backend Engineering", skills=["Python"])
            al.get_live_listings("Backend Engineering", skills=["Go"])
            al.get_live_listings("Backend Engineering", skills=["Python"])
        check("adzuna: the cache key includes the skills (Python and Go searches are separate; the repeat is served from the cache)",
              what == ["backend developer Python", "backend developer Go"])

    with app.app_context():
        fresh()
        seen = []

        def jwith(url, json=None, timeout=None):
            seen.append(json["keywords"])
            return Resp(200, {"jobs": [joo("DevOps Engineer", "Skill Co")]})
        with patch("app.pipeline.jooble_listings.requests.post", side_effect=jwith):
            r = jl.get_jooble_listings("DevOps", skills=["Docker", "Kubernetes", "Git"])
        check("jooble: with skills the first keywords are '<role> <skill> <skill> fresher' and matched_on lists them",
              seen[0] == "devops engineer Docker Kubernetes fresher" and r["matched_on"] == ["Docker", "Kubernetes"])
        fresh()
        seen.clear()

        def jnone(url, json=None, timeout=None):
            seen.append(json["keywords"])
            return Resp(200, {"jobs": []}) if "Docker" in json["keywords"] else Resp(200, {"jobs": [joo("DevOps Engineer", "Plain Co")]})
        with patch("app.pipeline.jooble_listings.requests.post", side_effect=jnone):
            r = jl.get_jooble_listings("DevOps", skills=["Docker"])
        check("jooble: skills that find nothing fall back to the plain search ('devops engineer fresher'), no matched_on",
              seen[-1] == "devops engineer fresher" and [x["company"] for x in r["listings"]] == ["Plain Co"] and "matched_on" not in r)

    with app.app_context():
        fresh()
        asked = []

        def a_stub(career_path, skills=()):
            asked.append(("adzuna", list(skills)))
            return {"listings": [{"title": "Backend Developer", "company": "A", "location": "X", "url": "https://adz.test/1"}], "unavailable": False, "matched_on": ["Python"]}

        def j_stub(career_path, skills=()):
            asked.append(("jooble", list(skills)))
            return {"listings": [{"title": "Python Developer", "company": "B", "location": "Y", "url": "https://jooble.test/2"}], "unavailable": False, "matched_on": ["Python", "SQL"]}
        with patch("app.pipeline.adzuna_listings.get_live_listings", a_stub), patch("app.pipeline.jooble_listings.get_jooble_listings", j_stub):
            r = lj.get_live_job_listings("Backend Engineering", skills=["Python", "SQL"])
            plain = lj.get_live_job_listings("Backend Engineering")
        check("combined: both sources receive the skills (first call) and none when there are none (second call)",
              sorted(asked[:2]) == [("adzuna", ["Python", "SQL"]), ("jooble", ["Python", "SQL"])]
              and sorted(asked[2:]) == [("adzuna", []), ("jooble", [])])
        check("combined: matched_on is the skills any source searched with, without repeats (Python, SQL)",
              r["matched_on"] == ["Python", "SQL"])
        check("combined: the answer has the same keys with and without skills, plus matched_on",
              set(r) == set(plain) and "matched_on" in r and isinstance(plain["matched_on"], list))

    with app.app_context():
        fresh()
        hosts = []

        def record_get(url, params=None, timeout=None):
            hosts.append(url.split("/")[2])
            return Resp(200, adz_payload(("Backend Developer", "Acme")))

        def record_post(url, json=None, timeout=None):
            hosts.append(url.split("/")[2])
            return Resp(200, {"jobs": [joo("Python Developer", "Delta")]})
        with patch("app.pipeline.adzuna_listings.requests.get", side_effect=record_get), \
             patch("app.pipeline.jooble_listings.requests.post", side_effect=record_post):
            lj.get_live_job_listings("Backend Engineering", skills=["Python", "SQL"])
        check("no site is scraped: with skills the only hosts contacted are the Adzuna and Jooble APIs (never LinkedIn, Naukri or Indeed)",
              hosts and set(hosts) <= {"api.adzuna.com", "jooble.org"})

    # ------------------------------------------------------------ search links
    all_ok = True
    for path in CAREER_PATHS:
        links = lj.search_links(path)
        all_ok &= [(l["name"], l["kind"]) for l in links] == [("LinkedIn", "fresher"), ("Naukri", "fresher"), ("Indeed", "fresher"),
                                                              ("LinkedIn", "internship"), ("Naukri", "internship"), ("Indeed", "internship")]
        all_ok &= all(l["url"].startswith(("https://www.linkedin.com/jobs/search/?", "https://www.naukri.com/", "https://in.indeed.com/jobs?"))
                      and " " not in l["url"] for l in links)
    check("search links: every path gives fresher AND internship links for LinkedIn, Naukri and Indeed on fixed https hosts, no spaces", all_ok)
    ui = lj.search_links("UI/UX Design")
    check("search links: fresher links use the entry-level filters (LinkedIn f_E=1,2; Naukri experience=0; 'fresher' on Indeed)",
          ui[0]["url"].endswith("&f_E=1%2C2") and ui[1]["url"].endswith("-jobs?experience=0") and "q=UI+UX+designer+fresher" in ui[2]["url"])
    check("search links: internship links ask for interns (LinkedIn f_E=1; 'intern' in the phrase)",
          ui[3]["url"].endswith("&f_E=1") and "UI+UX+designer+intern" in ui[3]["url"] and "ui-ux-designer-intern-jobs" in ui[4]["url"]
          and "q=UI+UX+designer+intern" in ui[5]["url"])
    check("search links: the phrase is URL-encoded (no raw slash or space)", "keywords=UI+UX+designer&" in ui[0]["url"] and "ui-ux-designer-jobs" in ui[1]["url"])
    check("search links: nothing is fetched (the module has no HTTP client)", "requests" not in open(lj.__file__, encoding="utf-8").read())

    passed = sum(1 for _, ok in checks if ok)
    print(f"\n{passed}/{len(checks)} checks passed")
    sys.exit(0 if passed == len(checks) else 1)


if __name__ == "__main__":
    main()
