"""
Lightweight ATS (Applicant Tracking System) friendliness score - NOT a deep
PDF layout/structure analysis (multi-column detection, table linearization,
etc. would need much more than pdfplumber's basic text extraction gives).
Reuses signals already computed elsewhere in Phase 2: extraction quality,
standard section headers, and real skill-match density against the
target career path's required skills.

Deliberately conservative and explainable - every point deducted has a
specific, stated reason, rather than an opaque single number.
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


def compute_ats_score(extracted_text, matched_skills, required_skills):
    """
    Returns {"score": int (0-100), "reasons": [str, ...]} - reasons list
    both positive confirmations and specific deductions, so the score is
    never just an opaque number.
    """
    score = 100
    reasons = []

    text_lower = extracted_text.lower()

    # 1. Extraction quality - a proxy for "is this parseable as plain text
    # at all", the single most common real ATS failure mode.
    text_len = len(extracted_text.strip())
    if text_len < NEAR_ZERO_CHARS:
        score -= 40
        reasons.append(
            "Almost no text could be extracted from this PDF - it is likely "
            "image-based or scanned, which most ATS systems cannot read at "
            "all. Export from a plain document editor instead of a design "
            "tool or scanner."
        )
    elif text_len < SPARSE_CHARS:
        score -= 15
        reasons.append(
            "This resume has relatively little content. The PDF itself "
            "appears readable, but consider adding more detail (experience, "
            "projects, a summary) so ATS systems and recruiters have more "
            "to match against."
        )
    else:
        reasons.append("Resume text extracted cleanly - good sign for ATS parseability.")

    # 2. Standard section headers
    sections_found = [s for s in STANDARD_SECTIONS if s in text_lower]
    if len(sections_found) < 3:
        score -= 20
        reasons.append(
            f"Only {len(sections_found)} standard section headers found "
            f"(e.g. Experience, Education, Skills). ATS systems rely on "
            f"these to categorize your resume - consider adding clear, "
            f"conventional section headings."
        )
    else:
        reasons.append(f"Found {len(sections_found)} standard section headers - good structure.")

    # 3. Contact info
    if not EMAIL_PATTERN.search(extracted_text):
        score -= 15
        reasons.append("No email address detected - make sure your contact info is in plain text, not an image.")
    if not PHONE_PATTERN.search(extracted_text):
        score -= 10
        reasons.append("No phone number detected in a standard format.")

    # 4. Skill keyword density against the target role's real required skills
    if required_skills:
        match_ratio = len(matched_skills) / len(required_skills)
        if match_ratio < 0.3:
            score -= 15
            reasons.append(
                f"Only {len(matched_skills)}/{len(required_skills)} of this role's "
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
