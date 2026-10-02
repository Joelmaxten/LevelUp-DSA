"""
Extra skill names for resume skill extraction in "which path fits my resume" mode, on top
of the four survey categories the existing vocabulary is built from (languages, databases,
platforms, web frameworks - see resume_analyzer.get_full_skill_vocabulary, which is left
exactly as it was so the "does my resume fit my path" results don't change).

Two sources, both listed here so they can be reviewed in one place:
1. SURVEY_EXTRA_COLUMNS: the survey's other skill-like columns (survey_respondents
   dev_envs, so_tags, office_stack), minus names that are ambiguous as words
   (AMBIGUOUS_SURVEY_NAMES).
2. SUPPLEMENTAL_SKILLS: very common resume skills the 2025 survey has no column for at all
   (it dropped the 2024 MiscTech/ToolsTech questions), so they get no survey signal and
   count only as recognised skills and in the roadmap-content signal. Hand-written; short
   on purpose.

Matching is spaCy PhraseMatcher on lower-cased tokens (a whole-word match), plus the alias
table in skill_aliases.py (regex with word boundaries) for abbreviations. A name that is also
an ordinary word, or too short to match safely, is skipped rather than risked.
"""

SURVEY_EXTRA_COLUMNS = ("dev_envs", "so_tags", "office_stack")

# Present in the new survey columns but unsafe to match in free text.
AMBIGUOUS_SURVEY_NAMES = {
    "Cursor",               # also a SQL / UI word
    "Nano", "Wikis", "Markdown File", "Google Workspace",
    "uv", "RAG", "hostinger", "c++23", ".NET 8 or higher", "Large Language Model", "Google Gemini",
    "Linear",               # "linear algebra", "linear regression"
    "Bolt", "Zed", "Coda", "Trae", "Rider", "Aider", "Miro",    # ordinary words or names too short/generic to match safely
    "Cline and/or Roo", "Delphi 12+ Athens", "Lovable.dev", "Lucid (includes Lucidchart)", "Stack Overflow for Teams",
    "visionOS",             # survey answer labels that are not how a resume names the skill
}

# (canonical name as it would appear on a resume). pandas keeps its lower-case spelling.
SUPPLEMENTAL_SKILLS = {
    "Git", "TensorFlow", "PyTorch", "Keras", "pandas", "NumPy", "scikit-learn", "Matplotlib",
    "Linux", "Jenkins", "Selenium", "Postman", "Tableau", "Power BI", "Figma",
}
