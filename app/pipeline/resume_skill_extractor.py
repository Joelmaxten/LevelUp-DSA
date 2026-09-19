"""
Extracts known technical skills from resume text using spaCy's PhraseMatcher
seeded with real skills from the SO Survey 2025 (India) dataset - not
spaCy's generic statistical NER, which was tested and found unreliable for
this task (it misclassified "Python, React" as ORG and "PostgreSQL" as GPE
- see PROJECT_BIOGRAPHY.md). PhraseMatcher is spaCy's rule-based exact/
near-match component, seeded with a real, already-validated vocabulary
rather than a hand-invented list.

Also checks a small alias table (skill_aliases.py) for common abbreviations
("AWS", "JS", "K8s") that resumes use but the SO Survey vocabulary stores
under its full name - PhraseMatcher alone would otherwise miss these.
"""

import re

import spacy
from spacy.matcher import PhraseMatcher

from app.pipeline.skill_aliases import SKILL_ALIASES

_nlp = None
_matcher = None


def _get_matcher(skill_vocabulary):
    global _nlp, _matcher
    if _matcher is None:
        _nlp = spacy.load("en_core_web_sm")
        _matcher = PhraseMatcher(_nlp.vocab, attr="LOWER")
        patterns = [_nlp.make_doc(skill) for skill in skill_vocabulary]
        _matcher.add("SKILLS", patterns)
    return _nlp, _matcher


def _find_aliases(text):
    """Checks text for known abbreviations, returning their canonical skill names."""
    text_lower = text.lower()
    found = set()
    for alias, canonical in SKILL_ALIASES.items():
        if canonical is None:
            continue
        if re.search(rf"\b{re.escape(alias)}\b", text_lower):
            found.add(canonical)
    return found


def extract_skills(text, skill_vocabulary):
    """
    Returns the set of skills (canonical names from skill_vocabulary) found
    in text - both direct PhraseMatcher matches and alias-resolved
    abbreviations.
    """
    nlp, matcher = _get_matcher(skill_vocabulary)
    doc = nlp(text)
    matches = matcher(doc)

    found = set()
    for match_id, start, end in matches:
        span = doc[start:end]
        found.add(span.text)

    found |= _find_aliases(text)

    return found
