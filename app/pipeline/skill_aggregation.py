"""
Shared skill-frequency aggregation over SurveyRespondent rows, used by
both FAISS chunk generation (so_survey_chunks.py) and Phase 2's skill-gap
computation (resume_analyzer.py). Kept here rather than duplicated in
either module, since both need the same underlying "what are the top N
skills for this career path" computation, just for different purposes and
different N.
"""

from collections import Counter


def top_skills(respondents, attr, top_n=5):
    """
    respondents: a list of SurveyRespondent rows (already filtered to the
    relevant career path).
    attr: which skill column to aggregate - "languages", "databases",
    "platforms", or "webframes".
    Returns the top_n most common values, as a plain list (most common first).
    """
    counter = Counter()
    for r in respondents:
        counter.update(getattr(r, attr))
    return [skill for skill, _ in counter.most_common(top_n)]
