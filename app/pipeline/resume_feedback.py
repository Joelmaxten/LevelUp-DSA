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

import re

from app.config import Config
from app.pipeline import llm_client


def _build_prompt(resume_text, target_career_path, matched_skills, missing_skills):
    return f"""You are a career advisor giving feedback on a student's resume for
the target role: {target_career_path}

Their resume text:
{resume_text}

Skills they already have (relevant to this role): {', '.join(sorted(matched_skills)) or 'none identified'}
Skills they are missing (relevant to this role): {', '.join(sorted(missing_skills)) or 'none identified'}

Rules (these matter more than anything else):
- Base your feedback ONLY on the resume text and the two skill lists above.
- NEVER invent facts: no made-up numbers, percentages, metrics, dates, employers, projects, skills,
  technologies or certificates. If a bullet would be stronger with a measurable result, tell the student
  to add THEIR OWN real number and write the placeholder [your measured result] (it already stands for
  the whole figure, so do not add a % or units after it).
- A skill, tool or technology may be written as something the student HAS only if it appears in the
  resume text or in the "already have" list. Anything else may only be suggested as something to learn
  and, if they really used it, to add; never put it in a rewritten objective, skills list or project line
  as if it were theirs.
- If a project or job line has no technologies, dates or results, say what is missing and write the
  placeholders [technologies you used], [month year] or [your measured result]. Never fill them in.
- Do not say something is duplicated, redundant, missing or wrong unless you can quote the exact resume
  words that show it. If you cannot quote them, do not say it.
- When you mention a certificate, course or credential, copy its name exactly as the resume writes it.
- Keyword suggestions must come from the "missing" list above. Never suggest a keyword that already
  appears in the resume text or in the "already have" list. If fewer than 5 qualify, give fewer.
- Do not make claims about prices, free tiers or availability of services; name a service only if the
  advice needs it.

Provide:
1. 3-5 specific, line-level suggestions to improve the resume (wording,
   structure, or what to add/remove)
2. A 30-day action plan with EXACTLY four weekly milestones (Week 1 to Week 4) to close the
   skill gap above
3. Up to 8 keywords the student should add (from the missing skills list only)

Respond in plain text with clear headers for each of the three sections
(Resume Suggestions, 30-Day Action Plan, Keyword Suggestions). Do not use
markdown formatting or asterisks - plain headers and numbered/bulleted
lines using plain dashes are fine."""


_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent\b)", re.IGNORECASE)
_PLACEHOLDER = "[your measured result]"


def remove_unsupported_percentages(feedback, resume_text):
    """Replace every percentage in the feedback that does not appear in the resume with a placeholder.

    A model can still invent "improved accuracy by 35%" despite the prompt rules; a made-up figure on a
    resume is a lie the student might paste in, so this deterministic check removes it. Percentages the
    resume itself contains (for example a percentage from the education section) are kept."""
    supported = {m.group(1) for m in _PERCENT.finditer(resume_text or "")}
    return _PERCENT.sub(lambda m: m.group(0) if m.group(1) in supported else _PLACEHOLDER, feedback)


_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
_MONTH_YEAR = re.compile(
    r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|"
    r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?,?\s+((?:19|20)\d{2})\b", re.IGNORECASE)
_NUMERIC_MONTH_YEAR = re.compile(r"\b(0?[1-9]|1[0-2])\s*[/-]\s*((?:19|20)\d{2})\b")
_DATE_PLACEHOLDER = "[month year]"


def _month_years(text):
    """Every (month number, year) the text mentions, as 'Sep 2024', 'September 2024' or '09/2024'."""
    found = set()
    for m in _MONTH_YEAR.finditer(text or ""):
        found.add((_MONTHS.index(m.group(1).lower()[:3]) + 1, m.group(2)))
    for m in _NUMERIC_MONTH_YEAR.finditer(text or ""):
        found.add((int(m.group(1)), m.group(2)))
    return found


def remove_unsupported_dates(feedback, resume_text):
    """Replace every "Month Year" in the feedback that the resume does not contain with a placeholder.

    The resume itself may only say "2025"; a suggestion such as "Jan 2025 - Mar 2025" would be an invented date
    range. Month-years the resume does contain (in any of the written or 09/2024 forms) are kept."""
    supported = _month_years(resume_text)

    def swap(match):
        key = (_MONTHS.index(match.group(1).lower()[:3]) + 1, match.group(2))
        return match.group(0) if key in supported else _DATE_PLACEHOLDER
    return _MONTH_YEAR.sub(swap, feedback)


def clean_feedback(feedback, resume_text):
    """Deterministic guards run on every reply: made-up percentages and made-up month-year dates become placeholders."""
    text = remove_unsupported_percentages(feedback, resume_text)
    text = re.sub(re.escape(_PLACEHOLDER) + r"\s*(?:%|percent\b)", _PLACEHOLDER, text, flags=re.IGNORECASE)
    return remove_unsupported_dates(text, resume_text)


def generate_resume_feedback(resume_text, target_career_path, matched_skills, missing_skills):
    """
    Returns the LLM's feedback as plain text, ready to store directly in
    Resume.ai_feedback. The whole call is capped at Config.RESUME_FEEDBACK_BUDGET_S seconds (default 45;
    0 = no cap): past that it raises LLMError (a ValueError), which the routes treat as "no feedback", so
    the skill analysis is still saved and shown. Percentages and month-year dates not present in the resume are replaced (clean_feedback).
    """
    prompt = _build_prompt(resume_text, target_career_path, matched_skills, missing_skills)
    budget = float(getattr(Config, "RESUME_FEEDBACK_BUDGET_S", 0) or 0)
    text = llm_client.generate("resume", prompt, budget_s=budget or None)["text"]
    return clean_feedback(text, resume_text)
