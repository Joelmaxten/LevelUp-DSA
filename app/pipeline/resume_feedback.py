"""
Generates LLM-based resume feedback: line-by-line improvement suggestions,
a 30-day action plan, and keyword suggestions - per the master doc's Phase
2 report spec. Reuses gemini_client.py's retry/fallback logic (same
reasoning as roadmap_generator.py - see that module's docstring).

Per the same anti-hallucination principle as roadmap generation, the
prompt is explicitly grounded in the student's REAL extracted skills and
REAL computed gap - not asked to freely critique the resume from scratch,
which would risk generic or fabricated advice untethered to their actual
data.
"""

from app.pipeline.gemini_client import generate_with_retry


def _build_prompt(resume_text, target_career_path, matched_skills, missing_skills):
    return f"""You are a career advisor giving feedback on a student's resume for
the target role: {target_career_path}

Their resume text:
{resume_text}

Skills they already have (relevant to this role): {', '.join(sorted(matched_skills)) or 'none identified'}
Skills they are missing (relevant to this role): {', '.join(sorted(missing_skills)) or 'none identified'}

Base your feedback ONLY on the resume text and the skill lists above - do
not invent experience, projects, or skills the student didn't mention.

Provide:
1. 3-5 specific, line-level suggestions to improve the resume (wording,
   structure, or what to add/remove)
2. A 30-day action plan with concrete weekly milestones to close the
   skill gap above
3. 5-8 keywords the student should add to their resume to better match
   this role (draw these from the missing skills list where relevant)

Respond in plain text with clear headers for each of the three sections
(Resume Suggestions, 30-Day Action Plan, Keyword Suggestions). Do not use
markdown formatting or asterisks - plain headers and numbered/bulleted
lines using plain dashes are fine."""


def generate_resume_feedback(resume_text, target_career_path, matched_skills, missing_skills):
    """
    Returns the LLM's feedback as plain text, ready to store directly in
    Resume.ai_feedback.
    """
    prompt = _build_prompt(resume_text, target_career_path, matched_skills, missing_skills)
    return generate_with_retry(prompt)
