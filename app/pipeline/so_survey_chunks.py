"""
Generates FAISS-ready text chunks from SO Survey 2025 (India) respondent
data - one chunk per career path, summarizing the most common languages,
databases, platforms, and frameworks among respondents in that path.

Uses plain frequency, not TF-IDF: with only 10 career paths acting as
"documents," TF-IDF's inverse-document-frequency term explodes for rare
skills (e.g. Dart, used almost exclusively in Mobile, scored artificially
#1 across unrelated paths like Research), producing less accurate results
than simple frequency counts. TF-IDF needs many documents to behave well;
10 is too few. This was tested and confirmed before reverting to plain
frequency - see PROJECT_BIOGRAPHY.md.
"""

from app.pipeline.skill_aggregation import top_skills

TOP_N = 5  # top skills per category to include in each chunk


def _top_skills(respondents, attr):
    return top_skills(respondents, attr, top_n=TOP_N)


def generate_survey_chunks(respondents_by_path):
    """
    respondents_by_path: {career_path: [SurveyRespondent, ...]} - one entry
    per career path, built with survey_queries.respondents_for_path() (see
    scripts/rebuild_kb.py). NOT grouped by the stored
    survey_respondents.career_path column here: that column still holds the
    old 10 path names (so_survey_processor.py, which writes it, is out of
    scope for the career-path restructuring), so grouping on it directly
    would produce chunks tagged with stale names instead of the current 15.
    Returns a list of {text, career_paths, source} chunks, matching the same
    shape as roadmap_kb_processor.py's chunks, ready for embedding - exactly
    one chunk per key in respondents_by_path, even if that path's respondent
    list is empty.
    """
    chunks = []
    for path, rows in respondents_by_path.items():
        languages = _top_skills(rows, "languages")
        databases = _top_skills(rows, "databases")
        platforms = _top_skills(rows, "platforms")
        webframes = _top_skills(rows, "webframes")

        parts = [f"Among {len(rows)} Indian developers surveyed in {path},"]
        if languages:
            parts.append(f"the most commonly used programming languages are {', '.join(languages)}.")
        if databases:
            parts.append(f"Common databases include {', '.join(databases)}.")
        if platforms:
            parts.append(f"Frequently used platforms and tools include {', '.join(platforms)}.")
        if webframes:
            parts.append(f"Popular web frameworks include {', '.join(webframes)}.")

        text = " ".join(parts)

        chunks.append({
            "text": text,
            "career_paths": [path],
            "source": f"so_survey_2025_india/{path.replace(' / ', '_').replace(' ', '_')}",
        })

    return chunks
