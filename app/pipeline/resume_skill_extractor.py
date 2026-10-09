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

from app.pipeline.skill_aliases import EXTENDED_SKILL_ALIASES, SKILL_ALIASES
from app.pipeline.skill_matching import find_composite_parts

_nlp = None
_matchers = {}   # frozenset(vocabulary) -> PhraseMatcher: the original and the extended vocabulary each get one


def _get_matcher(skill_vocabulary):
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    key = frozenset(skill_vocabulary)
    if key not in _matchers:
        matcher = PhraseMatcher(_nlp.vocab, attr="LOWER")
        matcher.add("SKILLS", [_nlp.make_doc(skill) for skill in sorted(key)])
        _matchers[key] = matcher
    return _nlp, _matchers[key]


def _alias_pattern(alias):
    """
    The alias as a whole token. \ba plain word-boundary check is not enough: it treats "." and "-" as boundaries, so "js"
    matched inside "Node.js" and "ts" inside "Next.ts". An alias must not touch a word character,
    nor be joined to a word by a dot or hyphen on either side. "JS", "js," and "(JS)" still match.
    """
    return re.compile(rf"(?<![\w])(?<!\w[.\-])" + re.escape(alias) + r"(?![\w])(?![.\-]\w)")


def _find_aliases(text, aliases=SKILL_ALIASES):
    """Checks text for known abbreviations, returning their canonical skill names."""
    text_lower = text.lower()
    found = set()
    for alias, canonical in aliases.items():
        if canonical is None:
            continue
        if _alias_pattern(alias).search(text_lower):
            found.add(canonical)
    return found


def extract_skills(text, skill_vocabulary, extended_aliases=False):
    """
    Returns the set of skills (canonical names from skill_vocabulary) found
    in text - both direct PhraseMatcher matches and alias-resolved
    abbreviations. extended_aliases=True also resolves skill_aliases.EXTENDED_SKILL_ALIASES
    (only to names that are in skill_vocabulary); the default leaves behavior unchanged.
    """
    nlp, matcher = _get_matcher(skill_vocabulary)
    doc = nlp(text)
    matches = matcher(doc)

    found = set()
    for match_id, start, end in matches:
        span = doc[start:end]
        found.add(span.text)

    found |= _find_aliases(text)
    found |= find_composite_parts(text)   # "HTML", "CSS" as separate skills; skill_matching decides what they add up to
    if extended_aliases:
        found |= {c for c in _find_aliases(text, EXTENDED_SKILL_ALIASES) if c in skill_vocabulary}

    return found
