"""
Phase 2 core pipeline: extracts text from an uploaded resume PDF, extracts
known skills from that text (via resume_skill_extractor.py's PhraseMatcher,
seeded with the real SO Survey skill vocabulary), and computes a skill gap
against the required skills for a target career path (the top skills real
Indian developers in that path report having, ranked by combined frequency
across all 4 skill categories) -
literally "required skills minus student skills", per the master doc's
spec, using real aggregate data for "required" rather than a hand-curated
list.
"""

import pdfplumber

from app.models import SurveyRespondent
from app.pipeline.resume_skill_extractor import extract_skills

REQUIRED_SKILLS_TOP_N = 10  # more than the 5 used for FAISS chunks - a real
                             # gap comparison needs a fuller picture than a
                             # short descriptive sentence does


def extract_text_from_pdf(file_path):
    """Extracts all text from a PDF resume, page by page, joined with newlines."""
    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


def get_full_skill_vocabulary():
    """The complete set of known skills across all four SO Survey categories."""
    vocab = set()
    for r in SurveyRespondent.query.all():
        vocab.update(r.languages)
        vocab.update(r.databases)
        vocab.update(r.platforms)
        vocab.update(r.webframes)
    return vocab


def get_required_skills(career_path, overall_top_n=REQUIRED_SKILLS_TOP_N):
    """
    The overall_top_n most common skills for this career path, ranked by
    real frequency across ALL 4 categories combined (not top-N-per-category
    independently) - so a skill genuinely needs to be common among real
    respondents to appear, rather than every category contributing its own
    top 10 regardless of how rare those skills actually are. Fixes a real
    problem found in testing: per-category top-10 produced e.g. 7 different
    databases as "required", most of which are alternatives to each other,
    not a real combined checklist - see PROJECT_BIOGRAPHY.md.
    """
    from collections import Counter

    respondents = SurveyRespondent.query.filter_by(career_path=career_path).all()
    if not respondents:
        return set()

    combined_counter = Counter()
    for attr in ["languages", "databases", "platforms", "webframes"]:
        for r in respondents:
            combined_counter.update(getattr(r, attr))

    return {skill for skill, _ in combined_counter.most_common(overall_top_n)}


def analyze_resume(file_path, target_career_path):
    """
    Full Phase 2 pipeline for one resume: extract text, extract skills,
    compute the gap against the target career path's required skills.

    Returns {
        "extracted_text": str,
        "student_skills": set,
        "required_skills": set,
        "missing_skills": set,     # required - student (the actual gap)
        "matched_skills": set,     # required AND student (what they already have)
    }
    """
    text = extract_text_from_pdf(file_path)

    vocabulary = get_full_skill_vocabulary()
    student_skills = extract_skills(text, vocabulary)

    required_skills = get_required_skills(target_career_path)

    missing_skills = required_skills - student_skills
    matched_skills = required_skills & student_skills

    return {
        "extracted_text": text,
        "student_skills": student_skills,
        "required_skills": required_skills,
        "missing_skills": missing_skills,
        "matched_skills": matched_skills,
    }
