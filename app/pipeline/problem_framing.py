"""
Career-contextualised problem framing for the Skill DNA Map: one Gemini call that
rewrites ONLY the story around a canonical problem for a student's career path
(e.g. "your inventory API has a bug in its hash map logic" for a Full-Stack student).

The problem itself is never regenerated. Its statement and test cases are the
verified originals in DSAProblem; the model is asked for a short scenario paragraph
and nothing else, and the UI always shows that scenario ABOVE the untouched
original statement. So even a scenario that drifts can't change what the student is
asked to solve or what they're graded against. Reuses gemini_client.py's
retry/fallback, like roadmap generation and resume feedback.
"""

from app.pipeline.gemini_client import generate_with_retry

# A scenario is a short paragraph. Outside this range the model rambled, or returned
# an apology / empty text, and showing it would be worse than showing nothing.
MIN_NARRATIVE_CHARS = 60
MAX_NARRATIVE_CHARS = 900


def _build_prompt(title, topic, description, career_path):
    return f"""You are writing the opening scenario of a coding exercise for a student
preparing for a career in: {career_path}

The exercise is the standard problem "{title}" (topic: {topic}). Its exact technical
statement, which the student will also see printed right below your scenario, is:

{description}

Write ONE short scenario paragraph (2 to 4 sentences, under 90 words) that puts this
same task in a realistic situation from {career_path}: a bug to fix, a feature to
build, or a piece of data to process, as a working professional in that field might
meet it.

Rules:
- Rewrite only the story. The task itself must stay exactly the same: same inputs,
  same output, same rules, same goal. Do not add, remove, or change any requirement,
  constraint, number, or example.
- Refer to the inputs and outputs using the same words the statement uses, so the
  scenario lines up with the statement beneath it.
- Do not include code, worked examples, hints, or the name of the algorithm or data
  structure to use.
- Speak to the student as "you". Plain text only: one paragraph, no title, no bullet
  points, no markdown."""


def _clean(text):
    """Trim the model's reply to a single plain paragraph, or None if it isn't usable."""
    if "```" in text:
        return None
    text = " ".join(text.replace("**", "").replace("`", "").split()).lstrip("# ")
    if not (MIN_NARRATIVE_CHARS <= len(text) <= MAX_NARRATIVE_CHARS):
        return None
    return text


def generate_framing(title, topic, description, career_path):
    """
    Returns the scenario paragraph as plain text. Raises ValueError if Gemini fails
    (gemini_client's uniform error) or its reply isn't a usable paragraph; callers
    fall back to showing the original problem alone.
    """
    reply = generate_with_retry(_build_prompt(title, topic, description, career_path))
    narrative = _clean(reply)
    if narrative is None:
        raise ValueError("Gemini returned an unusable scenario.")
    return narrative
