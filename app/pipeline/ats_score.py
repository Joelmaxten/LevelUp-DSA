"""
Lightweight ATS (Applicant Tracking System) friendliness score - NOT a deep
PDF layout/structure analysis (multi-column detection, table linearization,
etc. would need much more than pdfplumber's basic text extraction gives).
Reuses signals already computed elsewhere in Phase 2: extraction quality,
standard section headers, content checks, and real skill-match density
against the target career path's required skills.

Deliberately conservative and explainable - every point deducted has a
specific, stated reason, rather than an opaque single number. Every check
reports a line, passed or deducted, so "Why this score" shows all of them.
It measures readability for a parser and a recruiter, not fit for a role.
"""

import re

STANDARD_SECTIONS = [
    "experience", "education", "skills", "projects",
    "summary", "objective", "certifications",
]

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_PATTERN = re.compile(r"(\+?\d[\d\-\s()]{8,}\d)")

# Two DIFFERENT thresholds, deliberately not conflated (an earlier version
# used one threshold for both and produced a misleading "this PDF might be
# broken" message on resumes that were just short, not actually broken -
# see PROJECT_BIOGRAPHY.md):
NEAR_ZERO_CHARS = 50   # true extraction failure - almost certainly an
                        # image-based/scanned PDF with no real text layer
SPARSE_CHARS = 500     # a real, readable resume that's just thin on content

# Deductions (points off 100) for the content checks, in one place.
MAX_PAGES = 2
PAGES_DEDUCTION = 10
NO_METRICS_DEDUCTION = 15
WEAK_START_DEDUCTION_EACH = 5       # per bullet ...
WEAK_START_DEDUCTION_MAX = 10       # ... up to this much
NO_LINKS_DEDUCTION = 8
LONG_PARAGRAPH_CHARS = 500          # a run of prose lines longer than this
LONG_PARAGRAPH_DEDUCTION = 10
MIN_DATES = 2
NO_DATES_DEDUCTION = 10
MIN_PROSE_LINE_CHARS = 40           # shorter lines are headings / contact lines, not prose

BULLET_MARKERS = ("•", "●", "▪", "◦", "‣", "–", "·", "-", "*")
WEAK_PHRASES = (
    "responsible for", "worked on", "helped", "assisted", "involved in", "duties included",
    "tasked with", "participated in", "worked with", "was part of",
)
LINK_PATTERN = re.compile(r"https?://|www\.|linkedin\.com/|github\.com/|gitlab\.com/", re.I)
_MONTHS = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
DATE_PATTERN = re.compile(rf"\b(?:19|20)\d\d\b|\b{_MONTHS}\s+\d{{2,4}}\b|\bpresent\b|\bcurrent\b", re.I)
YEAR_ONLY = re.compile(r"\b(?:19|20)\d\d\b")   # a bare year is a date, not a metric


def _without_noise(line):
    """A line with phone numbers, emails and bare years removed - digits there are not metrics."""
    return YEAR_ONLY.sub("", PHONE_PATTERN.sub("", EMAIL_PATTERN.sub("", line)))


def _lines(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


def _bullets_and_prose(text):
    """(bullet lines with the marker stripped, other lines long enough to be prose). The prose lines stand in for bullets when the PDF has no markers."""
    bullets, prose = [], []
    for line in _lines(text):
        if line.startswith(BULLET_MARKERS) and len(line) > 2:
            bullets.append(line.lstrip("".join(BULLET_MARKERS) + " ").strip())
        elif len(line) >= MIN_PROSE_LINE_CHARS:
            prose.append(line)
    return bullets, prose


def _longest_prose_run(text):
    """Characters in the longest run of consecutive non-bullet lines that are each prose-length."""
    best = run = 0
    for line in _lines(text):
        if len(line) >= MIN_PROSE_LINE_CHARS and not line.startswith(BULLET_MARKERS):
            run += len(line)
            best = max(best, run)
        else:
            run = 0
    return best


def _checks(extracted_text, page_count):
    """
    Every check as (points_deducted, reason). points_deducted is 0 when the check passed (or
    could not be run), so there is exactly one entry per check.
    """
    out = []
    text_lower = extracted_text.lower()

    # 1. Extraction quality - a proxy for "is this parseable as plain text
    # at all", the single most common real ATS failure mode.
    text_len = len(extracted_text.strip())
    if text_len < NEAR_ZERO_CHARS:
        out.append((40,
            "Almost no text could be extracted from this PDF - it is likely "
            "image-based or scanned, which most ATS systems cannot read at "
            "all. Export from a plain document editor instead of a design "
            "tool or scanner."))
    elif text_len < SPARSE_CHARS:
        out.append((15,
            "This resume has relatively little content. The PDF itself "
            "appears readable, but consider adding more detail (experience, "
            "projects, a summary) so ATS systems and recruiters have more "
            "to match against."))
    else:
        out.append((0, "Resume text extracted cleanly - good sign for ATS parseability."))

    # 2. Standard section headers
    sections_found = [s for s in STANDARD_SECTIONS if s in text_lower]
    if len(sections_found) < 3:
        out.append((20,
            f"Only {len(sections_found)} standard section headers found "
            f"(e.g. Experience, Education, Skills). ATS systems rely on "
            f"these to categorize your resume - consider adding clear, "
            f"conventional section headings."))
    else:
        out.append((0, f"Found {len(sections_found)} standard section headers - good structure."))

    # 3. Contact info - email and phone are reported separately
    if EMAIL_PATTERN.search(extracted_text):
        out.append((0, "Email address found in plain text."))
    else:
        out.append((15, "No email address detected - make sure your contact info is in plain text, not an image."))
    if PHONE_PATTERN.search(extracted_text):
        out.append((0, "Phone number found in a standard format."))
    else:
        out.append((10, "No phone number detected in a standard format."))

    # 4. Length
    if page_count is None:
        out.append((0, "Page count could not be read, so length was not checked."))
    elif page_count > MAX_PAGES:
        out.append((PAGES_DEDUCTION,
            f"The resume is {page_count} pages. Recruiters skim - keep it to {MAX_PAGES} pages or fewer."))
    else:
        out.append((0, f"{page_count} page{'s' if page_count != 1 else ''} - within the {MAX_PAGES}-page guideline."))

    bullets, prose = _bullets_and_prose(extracted_text)
    achievement_lines = bullets or prose

    # 5. Numbers / metrics
    if not achievement_lines:
        out.append((0, "No bullet points or descriptive lines found, so numbers and metrics were not checked."))
    elif any(re.search(r"\d", _without_noise(line)) for line in achievement_lines):
        out.append((0, "Numbers or metrics found in your bullets - good, they show impact."))
    else:
        out.append((NO_METRICS_DEDUCTION,
            "No numbers or metrics in any bullet (e.g. '40% faster', '3 services', '2,000 users'). "
            "Measurable results are what recruiters look for."))

    # 6. Weak opening phrases
    weak = [b for b in bullets if b.lower().startswith(WEAK_PHRASES)]
    if weak:
        points = min(WEAK_START_DEDUCTION_MAX, WEAK_START_DEDUCTION_EACH * len(weak))
        out.append((points,
            f"{len(weak)} bullet{'s' if len(weak) != 1 else ''} start with a weak phrase such as 'Responsible for' or "
            f"'Worked on' (e.g. \"{weak[0][:50]}\"). Start with a strong verb: Built, Led, Reduced."))
    else:
        out.append((0, "No bullets start with weak phrases like 'Responsible for' or 'Worked on'."))

    # 7. Links
    if LINK_PATTERN.search(extracted_text):
        out.append((0, "A profile or project link (LinkedIn, GitHub, website) was found."))
    else:
        out.append((NO_LINKS_DEDUCTION, "No links found. Add your LinkedIn, GitHub or a project URL as visible text."))

    # 8. Very long paragraphs
    longest = _longest_prose_run(extracted_text)
    if longest > LONG_PARAGRAPH_CHARS:
        out.append((LONG_PARAGRAPH_DEDUCTION,
            f"A block of running text is about {longest} characters long. Break it into short bullets - "
            f"dense paragraphs are hard to skim."))
    else:
        out.append((0, "No overly long paragraphs - the text is easy to skim."))

    # 9. Dates
    if len(DATE_PATTERN.findall(extracted_text)) < MIN_DATES:
        out.append((NO_DATES_DEDUCTION,
            "Few or no dates found. Add start and end dates (e.g. 'Jun 2023 - Present') to experience, "
            "projects and education."))
    else:
        out.append((0, "Dates found on your experience or education."))

    return out


def _structure_checks(extracted_text, page_count=None):
    """
    The role-independent checks. Returns (score before clamping, reasons), one reason per check;
    a deduction is shown as "-15 points: ...".
    """
    checks = _checks(extracted_text, page_count)
    score = 100 - sum(points for points, _ in checks)
    reasons = [f"-{points} points: {reason}" if points else reason for points, reason in checks]
    return score, reasons


def compute_ats_structure_score(extracted_text, page_count=None):
    """
    The same score without the role keyword-density part - for a resume that has no target
    career path yet. Returns {"score": int (0-100), "reasons": [str, ...]}.
    """
    score, reasons = _structure_checks(extracted_text, page_count)
    return {"score": max(0, min(100, score)), "reasons": reasons}


def compute_ats_score(extracted_text, matched_skills, required_skills, page_count=None):
    """
    Returns {"score": int (0-100), "reasons": [str, ...]} - one reason per check, passed or
    deducted, so the score is never just an opaque number.
    """
    score, reasons = _structure_checks(extracted_text, page_count)

    # 10. Skill keyword density against the target role's real required skills
    if required_skills:
        match_ratio = len(matched_skills) / len(required_skills)
        if match_ratio < 0.3:
            score -= 15
            reasons.append(
                f"-15 points: Only {len(matched_skills)}/{len(required_skills)} of this role's "
                f"commonly-required skills appear in your resume - low keyword "
                f"overlap can hurt ATS ranking even if you have the skills."
            )
        else:
            reasons.append(
                f"{len(matched_skills)}/{len(required_skills)} commonly-required "
                f"skills for this role are present - good keyword coverage."
            )

    score = max(0, min(100, score))

    return {"score": score, "reasons": reasons}
