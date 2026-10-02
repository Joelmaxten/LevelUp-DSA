"""
Smoke test for live Adzuna job listings: app/pipeline/adzuna_listings.py's
normalization/caching/failure handling, GET /resume/listings, and the
salary-summary medians-only change. No real Adzuna, Gemini, or YouTube
call - every HTTP/Gemini call is patched with unittest.mock.patch.

Usage:
    PYTHONPATH=. python scripts/smoke_test_adzuna.py [--keep]

By default, the one throwaway user + resume/skill-gap rows this script
creates are deleted at the end, pass or fail. --keep leaves them (prints
the user's email and a password that satisfies the signup password rules).

Exits non-zero if any check fails.
"""
import random
import sys
import time as time_module
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv
load_dotenv()

import requests as requests_module
from fpdf import FPDF

from scripts._csrf import enable_csrf_client
from app import create_app, db
from app.models import CareerProfile, Resume, SkillGap, User
from app.pipeline import adzuna_listings as al
from app.pipeline.career_path_registry import CAREER_PATHS
from app.pipeline.salary_matching import format_salary_range_summary

PASSWORD = "SmokeTest#123"
FAKE_APP_ID = "SECRET_APP_ID_zzz999"
FAKE_APP_KEY = "SECRET_APP_KEY_yyy888"

checks = []


def check(description, condition):
    checks.append((description, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {description}")


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, json_error=None):
        self.status_code = status_code
        self._json_data = json_data
        self._json_error = json_error

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._json_data


def make_test_pdf(path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for line in ["Jane Doe", "Software Engineer", "", "SKILLS", "Python, SQL, Docker, AWS, Git"]:
        pdf.cell(0, 10, text=line, new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(path))


def main():
    keep = "--keep" in sys.argv
    app = create_app()
    enable_csrf_client(app)
    app.config["ADZUNA_APP_ID"] = FAKE_APP_ID
    app.config["ADZUNA_APP_KEY"] = FAKE_APP_KEY

    with app.app_context():
        db.create_all()

        # ---------------------------------------------------------------
        check("SEARCH_TERMS covers every CAREER_PATHS entry", set(al.SEARCH_TERMS) == set(CAREER_PATHS))

        # ---------------------------------------------------------------
        # successful response: midpoint, predicted flag, missing salary
        # ---------------------------------------------------------------
        al._cache.clear()
        success_payload = {
            "results": [
                {
                    "title": "Backend Developer", "company": {"display_name": "Acme Co"},
                    "location": {"display_name": "Bengaluru, India"},
                    "redirect_url": "https://example.com/job/1",
                    "salary_min": 600000, "salary_max": 900000, "salary_is_predicted": "1",
                },
                {
                    "title": "Backend Engineer II", "company": {"display_name": "Beta Inc"},
                    "location": {"display_name": "Pune, India"},
                    "redirect_url": "https://example.com/job/2",
                    "salary_is_predicted": "0",
                    # no salary_min/salary_max at all
                },
            ],
        }
        with patch("app.pipeline.adzuna_listings.requests.get", return_value=FakeResponse(200, success_payload)) as mock_get:
            result = al.get_live_listings("Backend Engineering")
        check("successful response: not unavailable", result["unavailable"] is False)
        check("successful response: 2 listings", len(result["listings"]) == 2)
        check("successful response: midpoint computed correctly", result["listings"][0]["salary_estimate"] == 750000)
        check("successful response: salary_is_predicted True parsed from '1'", result["listings"][0]["salary_is_predicted"] is True)
        check("successful response: missing salary -> salary_estimate None", result["listings"][1]["salary_estimate"] is None)
        check("successful response: salary_is_predicted False parsed from '0'", result["listings"][1]["salary_is_predicted"] is False)
        check("successful response: HTTP called exactly once", mock_get.call_count == 1)

        dump = repr(result)
        check("Adzuna app_id never appears in the returned value", FAKE_APP_ID not in dump)
        check("Adzuna app_key never appears in the returned value", FAKE_APP_KEY not in dump)

        # ---------------------------------------------------------------
        # cache: second call doesn't re-hit HTTP; expires after TTL
        # ---------------------------------------------------------------
        with patch("app.pipeline.adzuna_listings.requests.get", return_value=FakeResponse(200, success_payload)) as mock_get2:
            result_cached = al.get_live_listings("Backend Engineering")
        check("cache: second call served from cache (no HTTP call)", mock_get2.call_count == 0)
        check("cache: cached result matches original", result_cached == result)

        future = time_module.monotonic() + al.CACHE_TTL_SECONDS + 1
        with patch("app.pipeline.adzuna_listings.time.monotonic", return_value=future):
            with patch("app.pipeline.adzuna_listings.requests.get", return_value=FakeResponse(200, success_payload)) as mock_get3:
                al.get_live_listings("Backend Engineering")
        check("cache: expires after TTL (HTTP called again)", mock_get3.call_count == 1)

        # ---------------------------------------------------------------
        # failure modes: timeout, 500, bad JSON, missing keys - all
        # "unavailable", none raise
        # ---------------------------------------------------------------
        al._cache.clear()
        with patch("app.pipeline.adzuna_listings.requests.get", side_effect=requests_module.exceptions.Timeout("boom")):
            r = al.get_live_listings("DevOps")
        check("timeout: returns unavailable, does not raise", r == {"listings": [], "unavailable": True})

        al._cache.clear()
        with patch("app.pipeline.adzuna_listings.requests.get", return_value=FakeResponse(500)):
            r = al.get_live_listings("DevOps")
        check("HTTP 500: returns unavailable, does not raise", r == {"listings": [], "unavailable": True})

        al._cache.clear()
        with patch("app.pipeline.adzuna_listings.requests.get", return_value=FakeResponse(200, json_error=ValueError("bad json"))):
            r = al.get_live_listings("DevOps")
        check("bad JSON: returns unavailable, does not raise", r == {"listings": [], "unavailable": True})

        al._cache.clear()
        with patch("app.pipeline.adzuna_listings.requests.get", return_value=FakeResponse(200, {"results": [{"title": "X"}]})):
            r = al.get_live_listings("DevOps")  # missing redirect_url
        check("missing key: returns unavailable, does not raise", r == {"listings": [], "unavailable": True})

        # failures are cached only briefly, not for the full TTL
        al._cache.clear()
        with patch("app.pipeline.adzuna_listings.requests.get", return_value=FakeResponse(500)):
            al.get_live_listings("DevOps")
        future_short = time_module.monotonic() + al.FAILURE_CACHE_TTL_SECONDS + 1
        with patch("app.pipeline.adzuna_listings.time.monotonic", return_value=future_short):
            with patch("app.pipeline.adzuna_listings.requests.get", return_value=FakeResponse(200, success_payload)) as mock_get4:
                al.get_live_listings("DevOps")
        check("failure cache expires quickly (short TTL), not the full 6h", mock_get4.call_count == 1)
        al._cache.clear()

        # ---------------------------------------------------------------
        # salary summary: medians only, under 80 chars, never raises
        # ---------------------------------------------------------------
        both = {
            "job_postings": {"count": 42, "min": 300000, "max": 1800000, "median": 650000, "currency": "INR"},
            "survey_respondents": {
                "count": 10, "min": 10000, "max": 90000, "median": 45000, "currency": "USD",
                "approx_inr": {"min": 875000, "max": 7875000, "median": 3937500},
            },
        }
        one_source = {"job_postings": both["job_postings"], "survey_respondents": None}
        none_source = {"job_postings": None, "survey_respondents": None}

        s_both = format_salary_range_summary(both)
        s_one = format_salary_range_summary(one_source)
        s_none = format_salary_range_summary(none_source)
        check("salary summary (both sources) under 80 chars", len(s_both) < 80)
        check("salary summary (both sources) uses medians, no range dash", s_both == "Postings: Rs650K/yr | Survey (approx): Rs3937K/yr")
        check("salary summary (one source) under 80 chars", len(s_one) < 80)
        check("salary summary (no sources) under 80 chars and doesn't raise", len(s_none) < 80)

        # ---------------------------------------------------------------
        # route: 401 logged out, 400 unknown/missing path, 200 otherwise
        # ---------------------------------------------------------------
        suffix = random.randint(100000, 999999)
        email = f"adzunatest{suffix}@example.com"
        user = User(name="Adzuna Test", email=email)
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()

        profile = CareerProfile(
            user_id=user.id,
            career_ranking=[
                {"career_path": p, "score": (1 if p == "Backend Engineering" else 0), "confidence_pct": 0.0}
                for p in CAREER_PATHS
            ],
            conversation_signals={},
        )
        db.session.add(profile)
        db.session.commit()

        with app.test_client() as client:
            resp = client.get("/resume/listings?career_path=Backend Engineering")
            check("/resume/listings: 401 when logged out", resp.status_code == 401)

            client.post("/login", json={"email": email, "password": PASSWORD})

            resp = client.get("/resume/listings?career_path=Not A Real Path")
            check(
                "/resume/listings: 400 for an unknown path",
                resp.status_code == 400 and resp.get_json()["error"] == "invalid_career_path",
            )

            resp = client.get("/resume/listings")
            check("/resume/listings: 400 for a missing path", resp.status_code == 400)

            with patch("app.routes.resume.get_live_listings", return_value={"listings": [], "unavailable": False}) as mock_route:
                resp = client.get("/resume/listings?career_path=Backend Engineering")
                body = resp.get_json()
                check("/resume/listings: 200 for a valid path", resp.status_code == 200)
                check("/resume/listings: response shape", set(body) == {"career_path", "listings", "unavailable"})
                mock_route.assert_called_once_with("Backend Engineering")

            # ------------------------------------------------------------
            # /resume/upload and /resume/latest: still valid, and never
            # call Adzuna (verified by patching the real HTTP call and
            # asserting it was never hit across both requests).
            # ------------------------------------------------------------
            pdf_path = Path("scratch/_smoke_test_adzuna_resume.pdf")
            pdf_path.parent.mkdir(exist_ok=True)
            make_test_pdf(pdf_path)

            with patch("app.pipeline.adzuna_listings.requests.get") as mock_adzuna_http, \
                 patch("app.routes.resume.generate_resume_feedback", return_value="stub feedback"):
                with open(pdf_path, "rb") as f:
                    resp = client.post("/resume/upload", data={
                        "resume": (f, "resume.pdf"), "target_career_path": "Backend Engineering",
                    }, content_type="multipart/form-data")
                upload_body = resp.get_json()
                check("/resume/upload: still 201", resp.status_code == 201)
                check("/resume/upload: response has no 'listings' key", upload_body is not None and "listings" not in upload_body)
                check("/resume/upload: salary_insights has no sample_listings key", "sample_listings" not in (upload_body or {}).get("salary_insights", {}))
                check("/resume/upload: never called Adzuna", mock_adzuna_http.call_count == 0)

                resp = client.get("/resume/latest")
                latest_body = resp.get_json()
                check("/resume/latest: still 200", resp.status_code == 200)
                check("/resume/latest: response has no 'listings' key", latest_body is not None and "listings" not in latest_body)
                check("/resume/latest: never called Adzuna", mock_adzuna_http.call_count == 0)

            pdf_path.unlink(missing_ok=True)

        # ---------------------------------------------------------------
        # cleanup
        # ---------------------------------------------------------------
        if keep:
            print()
            print("--keep: demo user left in place.")
            print(f"  email:    {email}")
            print(f"  password: {PASSWORD}")
        else:
            Resume.query.filter_by(user_id=user.id).delete()
            SkillGap.query.filter_by(user_id=user.id).delete()
            CareerProfile.query.filter_by(user_id=user.id).delete()
            User.query.filter_by(id=user.id).delete()
            db.session.commit()
            print()
            print("Cleaned up all test rows.")

    print()
    passed = sum(1 for _, ok in checks if ok)
    total = len(checks)
    print(f"{passed}/{total} checks passed.")
    if passed != total:
        print()
        print("Failures:")
        for desc, ok in checks:
            if not ok:
                print(f"  - {desc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
