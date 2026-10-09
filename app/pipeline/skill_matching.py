"""
Rules for comparing a resume's skills with a career path's required skills, kept in this one
file so they are not scattered across the extractor, the analyzer and the routes.

  EXCLUDED_TOOLING   package managers / build tools: never counted as a required skill
  COMPOSITE_SKILLS   one required name that really means several ("HTML/CSS")
  IMPLIED_BY         a required skill that any one of several other skills proves ("SQL")
"""

import re

# Tooling every developer in that ecosystem has; asking a student to "learn npm" is not a skill gap.
# Compared case-insensitively. Excluded before the top-N cut, so the required list is still N long.
EXCLUDED_TOOLING = frozenset({
    "npm", "pip", "yarn", "pnpm", "homebrew", "cargo", "nuget", "composer",
    "maven", "gradle", "make", "webpack", "vite",
})

# required name -> the parts that must ALL be found. All parts found = matched; some = partly matched.
COMPOSITE_SKILLS = {
    "HTML/CSS": ("HTML", "CSS"),
}

# required name -> skills that each imply it
IMPLIED_BY = {
    "SQL": frozenset({"MySQL", "PostgreSQL", "SQLite", "Microsoft SQL Server", "MariaDB"}),
}

# How a composite's part is spelled on a resume (HTML5 / CSS3 count as HTML / CSS).
_PART_PATTERNS = {
    "HTML": re.compile(r"\bhtml5?\b", re.I),
    "CSS": re.compile(r"\bcss3?\b", re.I),
}


def is_excluded_tooling(skill):
    return skill.lower() in EXCLUDED_TOOLING


def find_composite_parts(text):
    """The composite parts ("HTML", "CSS") that appear as words in the resume text."""
    return {part for part, pattern in _PART_PATTERNS.items() if pattern.search(text)}


def resolve_required(required_skills, student_skills):
    """
    Compares required skills with the student's. Returns (matched, missing, partial):
      matched  required skills the student has (directly, via every part of a composite, or via an implying skill)
      missing  every other required skill - a partly matched composite is still missing
      partial  {composite: {"found": [parts], "missing": [parts]}} for composites with some but not all parts
    """
    student = set(student_skills)
    lowered = {s.lower() for s in student}
    matched, missing, partial = set(), set(), {}
    for skill in required_skills:
        if skill in student:
            matched.add(skill)
            continue
        parts = COMPOSITE_SKILLS.get(skill)
        if parts:
            found = [p for p in parts if p.lower() in lowered]
            if len(found) == len(parts):
                matched.add(skill)
                continue
            if found:
                partial[skill] = {"found": found, "missing": [p for p in parts if p not in found]}
        elif any(i in student for i in IMPLIED_BY.get(skill, ())):
            matched.add(skill)
            continue
        missing.add(skill)
    return matched, missing, partial
