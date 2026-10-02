"""
"Which career path fits my resume?" - ranks the 15 career paths for a set of resume skills.
Everything in the first half of this module is pure and deterministic (no Flask, no
database, no model): data goes in as plain dicts/lists, a ranking comes out. The loaders at
the bottom fetch the data from the survey table and the FAISS knowledge base, cache it, and
call the pure functions.

Two independent signals:

1. Survey signal (paths with at least MIN_RESPONDENTS survey respondents). For every skill
   listed in any of the seven survey skill columns, share_in_path is the fraction of that
   path's respondents who list it and share_overall the fraction of ALL respondents who do;
   lift = share_in_path / share_overall. Only skills with share_in_path >= MIN_SHARE count
   (a skill a handful of people in the path mention proves little). A path's survey score is
   the sum of lift x share_in_path over the resume's skills that qualify - so a skill that is
   both common in the path AND distinctive of it (Python for ML, but not Git for everyone)
   contributes most.

2. Roadmap signal (every path). A summary of the resume's skills is embedded, the top
   RETRIEVE_K knowledge-base chunks are retrieved with no path filter, and each path gets the
   number of those chunks tagged with it divided by the path's total number of tagged chunks,
   so a path with a huge roadmap.sh folder doesn't win on volume.

Output, in two lists (never merged, because their evidence differs):
- List A: paths with enough respondents, ranked by an even blend of the two signals, each
  min-max normalised over List A.
- List B: thin paths (fewer than MIN_RESPONDENTS), ranked by the roadmap signal alone, and
  ONLY those with at least THIN_PATH_MIN_HITS of the RETRIEVE_K retrieved chunks tagged with
  them (an evidence floor, see below). A thin path gets a rank, its matched skills and its
  respondent count, but no fit percentage: a score from a handful of chunks looks more precise
  than it is. If no thin path passes, List B is empty.
List A rows carry fit_pct, the row's score relative to the TOP of the list (the top row is
100). Rows within NEAR_TIE of the top of List A are reported together as near-ties. Fewer than
MIN_SKILLS recognised skills gives an insufficient_data result instead of a ranking.

Evidence floor (THIN_PATH_MIN_HITS = 6 of 30, i.e. 20% of the retrieved chunks): the 30
retrieved chunks spread over 15 paths average 2 per path by chance. scripts/
measure_thin_path_floor.py measured three developer resumes and two controls with generic
skills (Excel, Word, Tally...): the counts for paths the resume has nothing to do with reached
4 (Cybersecurity for a Python/SQL resume, QA for a JavaScript one); counts of 5 or more only
appeared where the skills do relate to the path (Data Analytics for Excel or pandas, UI/UX
for Photoshop). 6 is three times the chance level and above every unrelated count seen. It was
not tuned to any one resume; UI/UX at 5 for Photoshop falls just below it.

The constants below are fixed design choices, not tuned to any example resume.
"""
from collections import Counter

MIN_RESPONDENTS = 30
MIN_SHARE = 0.10
NEAR_TIE = 0.15
MIN_SKILLS = 3
RETRIEVE_K = 30
THIN_PATH_MIN_HITS = 6
SURVEY_WEIGHT = 0.5
ROADMAP_WEIGHT = 0.5

BASIS_BOTH = "survey and roadmap content"
BASIS_ROADMAP_ONLY = "based on roadmap content only"

SURVEY_SKILL_ATTRS = ("languages", "databases", "platforms", "webframes", "dev_envs", "so_tags", "office_stack")


# ------------------------------------------------------------------ pure functions

def respondent_skills(respondent):
    """The set of skills one respondent lists, across every survey skill column (a respondent counts once per skill)."""
    skills = set()
    for attr in SURVEY_SKILL_ATTRS:
        skills.update(getattr(respondent, attr, None) or [])
    return skills


def build_survey_stats(skills_by_path, all_skill_sets):
    """
    skills_by_path: {path: [set of skills per respondent in that path]};
    all_skill_sets: [set of skills per respondent] for the whole survey.
    Returns {"n_overall", "overall": Counter, "paths": {path: {"n", "counts": Counter}}}.
    """
    paths = {}
    for path, sets in skills_by_path.items():
        counts = Counter()
        for skills in sets:
            counts.update(skills)
        paths[path] = {"n": len(sets), "counts": counts}
    overall = Counter()
    for skills in all_skill_sets:
        overall.update(skills)
    return {"n_overall": len(all_skill_sets), "overall": overall, "paths": paths}


def survey_scores(resume_skills, stats):
    """
    {path: {"score": float, "matched": [{"skill", "lift", "share"}...]}} for every path with at
    least MIN_RESPONDENTS respondents. matched is sorted by contribution, largest first.
    """
    result = {}
    n_overall = stats["n_overall"]
    for path, data in stats["paths"].items():
        n = data["n"]
        if n < MIN_RESPONDENTS:
            continue
        matched = []
        for skill in resume_skills:
            in_path = data["counts"].get(skill, 0)
            overall = stats["overall"].get(skill, 0)
            if not in_path or not overall:
                continue
            share = in_path / n
            if share < MIN_SHARE:
                continue
            lift = share / (overall / n_overall)
            matched.append({"skill": skill, "lift": lift, "share": share})
        matched.sort(key=lambda m: (-(m["lift"] * m["share"]), m["skill"]))
        result[path] = {"score": sum(m["lift"] * m["share"] for m in matched), "matched": matched}
    return result


def roadmap_scores(hits, path_totals):
    """
    hits: the retrieved chunks (dicts with "career_paths"); path_totals: {path: number of
    chunks tagged with it}. Returns {path: hits tagged with path / path's total chunks}.
    """
    counts = Counter(path for chunk in hits for path in chunk.get("career_paths", []))
    return {path: counts.get(path, 0) / total for path, total in path_totals.items() if total}


def roadmap_matched_skills(resume_skills, hits, path):
    """Resume skills named in the title or text of the retrieved chunks tagged with `path`."""
    text = " ".join(f"{c.get('title', '')} {c.get('text', '')}" for c in hits if path in c.get("career_paths", [])).lower()
    return sorted(s for s in resume_skills if s.lower() in text)


def _min_max(values):
    if not values:
        return {}
    lo, hi = min(values.values()), max(values.values())
    if hi == lo:
        return {k: 0.0 for k in values}
    return {k: (v - lo) / (hi - lo) for k, v in values.items()}


def _finish_list(entries, top_score):
    """entries: [{"path", "score", ...}] sorted best first -> rows with fit_pct relative to the top."""
    rows = []
    for e in entries:
        fit = 100.0 * e["score"] / top_score if top_score > 0 else 0.0
        rows.append({**{k: v for k, v in e.items() if k != "score"}, "fit_pct": round(fit, 1)})
    return rows


def near_ties(rows):
    """Paths within NEAR_TIE of the top row's fit; [] unless at least two."""
    if not rows:
        return []
    group = [r["path"] for r in rows if r["fit_pct"] >= 100.0 * (1 - NEAR_TIE)]
    return group if len(group) >= 2 else []


def rank_paths(resume_skills, stats, hits, path_totals):
    """
    The full ranking. resume_skills: set of recognised skill names. Returns
    {"insufficient_data": bool, "list_a": [...], "list_b": [...], "near_ties": {"a": [...], "b": [...]}}
    where each row is {"path", "fit_pct", "matched_skills", "respondent_count", "basis"}.
    Deterministic: ties on score are broken by path name.
    """
    skills = set(resume_skills)
    empty = {"insufficient_data": True, "list_a": [], "list_b": [], "near_ties": {"a": [], "b": []}}
    if len(skills) < MIN_SKILLS:
        return empty

    survey = survey_scores(skills, stats)
    roadmap = roadmap_scores(hits, path_totals)
    counts = {path: data["n"] for path, data in stats["paths"].items()}

    # List A: enough respondents -> blend of both signals.
    a_paths = sorted(survey)
    survey_norm = _min_max({p: survey[p]["score"] for p in a_paths})
    roadmap_norm = _min_max({p: roadmap.get(p, 0.0) for p in a_paths})
    a_entries = [{
        "path": p,
        "score": SURVEY_WEIGHT * survey_norm[p] + ROADMAP_WEIGHT * roadmap_norm[p],
        "matched_skills": [m["skill"] for m in survey[p]["matched"]],
        "respondent_count": counts.get(p, 0),
        "basis": BASIS_BOTH,
    } for p in a_paths]
    a_entries.sort(key=lambda e: (-e["score"], e["path"]))

    # List B: thin paths -> roadmap signal alone, and only above the evidence floor; rank only.
    hit_counts = Counter(path for chunk in hits for path in chunk.get("career_paths", []))
    b_paths = sorted(p for p in path_totals if p not in survey and hit_counts.get(p, 0) >= THIN_PATH_MIN_HITS)
    b_entries = [{
        "path": p,
        "score": roadmap.get(p, 0.0),
        "matched_skills": roadmap_matched_skills(skills, hits, p),
        "respondent_count": counts.get(p, 0),
        "basis": BASIS_ROADMAP_ONLY,
    } for p in b_paths]
    b_entries.sort(key=lambda e: (-e["score"], e["path"]))
    list_b = [{"rank": i, **{k: v for k, v in e.items() if k != "score"}} for i, e in enumerate(b_entries, start=1)]

    list_a = _finish_list(a_entries, a_entries[0]["score"] if a_entries else 0.0)
    if all(r["fit_pct"] == 0.0 for r in list_a) and not list_b:
        return empty     # nothing in the survey or the roadmaps relates to these skills
    return {"insufficient_data": False, "list_a": list_a, "list_b": list_b,
            "near_ties": {"a": near_ties(list_a), "b": []}}


def skills_summary(resume_skills):
    """The text that is embedded for the roadmap signal."""
    return "Resume skills: " + ", ".join(sorted(resume_skills))


# ------------------------------------------------------------------ loaders (database, index, model)

_stats_cache = None
_totals_cache = None


def load_survey_stats():
    """Per-path survey statistics from the database (needs an app context); cached for the process."""
    global _stats_cache
    if _stats_cache is None:
        from app.models import SurveyRespondent
        from app.pipeline.career_path_registry import CAREER_PATHS
        from app.pipeline.survey_queries import respondents_for_path
        everyone = [respondent_skills(r) for r in SurveyRespondent.query.order_by(SurveyRespondent.id).all()]
        by_path = {p: [respondent_skills(r) for r in respondents_for_path(p).order_by(SurveyRespondent.id).all()] for p in CAREER_PATHS}
        _stats_cache = build_survey_stats(by_path, everyone)
    return _stats_cache


def load_path_totals(chunks):
    """{path: number of knowledge-base chunks tagged with it}; cached for the process."""
    global _totals_cache
    if _totals_cache is None:
        from app.pipeline.career_path_registry import CAREER_PATHS
        counts = Counter(p for c in chunks for p in c.get("career_paths", []))
        _totals_cache = {p: counts.get(p, 0) for p in CAREER_PATHS}
    return _totals_cache


def fit_for_skills(resume_skills, index, chunks, stats=None, search=None):
    """
    Orchestrates one ranking: loads (cached) survey stats, retrieves the top RETRIEVE_K chunks
    for the skills summary with no path filter, and calls rank_paths. `search` is injectable for
    tests; it defaults to rag.search.
    """
    skills = set(resume_skills)
    if len(skills) < MIN_SKILLS:
        return rank_paths(skills, {"n_overall": 1, "overall": Counter(), "paths": {}}, [], {})
    if search is None:
        from app.pipeline.rag import search
    hits = search(skills_summary(skills), index, chunks, top_k=RETRIEVE_K, career_path=None)
    return rank_paths(skills, stats or load_survey_stats(), hits, load_path_totals(chunks))
