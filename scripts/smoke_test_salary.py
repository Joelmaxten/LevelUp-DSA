"""
Salary insights must not crash when the data tables are empty (a fresh database whose job_listings /
survey_respondents were never loaded). Regression test for IndexError in get_salary_insights.
Uses stubs, so it needs no database and no network.

Run: PYTHONPATH=. python scripts/smoke_test_salary.py
"""
import sys
from unittest import mock

from app.pipeline import salary_matching as sm

passed = failed = 0


def check(name, ok):
    global passed, failed
    if ok:
        passed += 1
        print(f"[PASS] {name}")
    else:
        failed += 1
        print(f"[FAIL] {name}")


class FakeQuery:
    """Chainable stand-in for a SQLAlchemy query that returns fixed rows."""
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *a, **k):
        return self

    def all(self):
        return list(self.rows)


class Col:
    """Stand-in for a model column: comparisons and isnot() just return something the fake query ignores."""
    def __ge__(self, other):
        return True

    def __le__(self, other):
        return True

    def isnot(self, other):
        return True

    def is_(self, other):
        return True

    def contains(self, other):
        return True


class Row:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def run(job_rows, survey_rows, path_rows=None):
    job_cls = type("JobListing", (), {"query": FakeQuery(job_rows), "career_paths": Col(),
                                      "annual_salary": Col(), "salary_suspicious": Col()})
    survey_cls = type("SurveyRespondent", (), {"query": FakeQuery(survey_rows), "converted_comp_yearly": Col()})
    with mock.patch.object(sm, "JobListing", job_cls), mock.patch.object(sm, "SurveyRespondent", survey_cls), \
            mock.patch.object(sm, "respondents_for_path", lambda path: FakeQuery(path_rows if path_rows is not None else survey_rows)):
        return sm.get_salary_insights("Data Science")


try:
    empty = run([], [])
    check("both tables empty: no crash, both sections None", empty == {"job_postings": None, "survey_respondents": None})
    check("both tables empty: the summary text says there is no salary data",
          sm.format_salary_range_summary(empty) == "No salary data available for this career path.")
except Exception as exc:   # the old code raised IndexError here
    check(f"both tables empty: no crash ({type(exc).__name__})", False)

jobs_only = run([Row(annual_salary=600000), Row(annual_salary=800000)], [])
check("job postings but no survey rows: postings section filled, survey None",
      jobs_only["survey_respondents"] is None and jobs_only["job_postings"]["median"] == 700000)

survey = [Row(converted_comp_yearly=v) for v in range(1000, 101000, 1000)]   # 100 respondents
full = run([], survey)
check("survey rows present: survey section filled with a median and an INR approximation",
      full["survey_respondents"] and full["survey_respondents"]["count"] >= 90
      and "approx_inr" in full["survey_respondents"])

print(f"{passed}/{passed + failed} checks passed")
if failed:
    print("FAILED")
    sys.exit(1)
