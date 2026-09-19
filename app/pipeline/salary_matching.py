"""
Salary and job-matching data for a target career path, drawn from two
distinct sources kept deliberately separate rather than merged into one
figure: India Jobs (real job postings, INR, skews entry-level/fresher -
this project's actual target audience) and SO Survey (self-reported
compensation from working developers, USD, skews toward more experience).
Merging these into one number would silently blend two different
populations and require a currency conversion that goes stale over time -
see PROJECT_BIOGRAPHY.md for the reasoning.
"""

from app.models import JobListing, SurveyRespondent

# Approximate USD -> INR rate. Hardcoded, not live-fetched (no currency API
# dependency for a display detail) - will go stale over time, same
# staleness risk as any hardcoded external figure in this project (see the
# Gemini model-name lesson in PROJECT_BIOGRAPHY.md). Update periodically;
# always presented as an approximation, never as a precise converted value.
USD_TO_INR_APPROX = 87.5


def get_salary_insights(career_path, max_listings=5):
    """
    Returns {
        "job_postings": {"count", "min", "max", "median", "currency": "INR"} or None,
        "survey_respondents": {"count", "min", "max", "median", "currency": "USD"} or None,
        "sample_listings": [{"job_title", "location", "annual_salary"}] - up to max_listings
            real job postings matching this career path, for "companies hiring" context.
    }
    Any section is None if there's no usable data for that career path.
    """
    job_listings = (
        JobListing.query
        .filter(JobListing.career_paths.contains([career_path]))
        .filter(JobListing.annual_salary.isnot(None))
        .filter(JobListing.salary_suspicious.is_(False))
        .all()
    )

    # SO Survey compensation data has real, serious outliers at both tails
    # (min observed: $1/year, max observed: $9.5M/year - self-reported survey
    # data with no validation, same class of problem as India Jobs' salary
    # mislabeling). Trim to the 1st-99th percentile of the FULL dataset
    # (not per-career-path, which would have too few points to percentile
    # meaningfully) before computing any per-path aggregate.
    all_comps = sorted([
        r.converted_comp_yearly for r in
        SurveyRespondent.query.filter(SurveyRespondent.converted_comp_yearly.isnot(None)).all()
    ])
    n_all = len(all_comps)
    lower_bound = all_comps[int(n_all * 0.01)]
    upper_bound = all_comps[int(n_all * 0.99)]

    survey_rows = (
        SurveyRespondent.query
        .filter_by(career_path=career_path)
        .filter(SurveyRespondent.converted_comp_yearly.isnot(None))
        .filter(SurveyRespondent.converted_comp_yearly >= lower_bound)
        .filter(SurveyRespondent.converted_comp_yearly <= upper_bound)
        .all()
    )

    def _stats(values, currency):
        if not values:
            return None
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        median = sorted_vals[n // 2] if n % 2 else (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
        return {
            "count": n,
            "min": round(min(values)),
            "max": round(max(values)),
            "median": round(median),
            "currency": currency,
        }

    job_posting_stats = _stats([j.annual_salary for j in job_listings], "INR")
    survey_stats = _stats([r.converted_comp_yearly for r in survey_rows], "USD")
    if survey_stats:
        survey_stats["approx_inr"] = {
            k: round(v * USD_TO_INR_APPROX) for k, v in survey_stats.items()
            if k in ("min", "max", "median")
        }

    sample_listings = [
        {"job_title": j.job_title, "location": j.location, "annual_salary": j.annual_salary}
        for j in job_listings[:max_listings]
    ]

    return {
        "job_postings": job_posting_stats,
        "survey_respondents": survey_stats,
        "sample_listings": sample_listings,
    }


def format_salary_range_summary(insights):
    """
    Compresses get_salary_insights()'s result into a short string that
    fits SkillGap.salary_range (db.String(80)). Falls back gracefully if
    either or both sources have no data for this career path.
    """
    parts = []

    jp = insights["job_postings"]
    if jp:
        parts.append(f"Postings: Rs{jp['min']//1000}K-{jp['max']//1000}K/yr")

    sr = insights["survey_respondents"]
    if sr:
        inr = sr["approx_inr"]
        parts.append(f"Survey (approx): Rs{inr['min']//1000}K-{inr['max']//1000}K/yr")

    if not parts:
        return "No salary data available for this career path."

    return " | ".join(parts)
