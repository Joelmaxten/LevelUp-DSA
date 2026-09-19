"""
Processes the Stack Overflow Developer Survey 2025 into clean, structured
rows for PostgreSQL, filtered to India respondents only - this project's
target audience is explicitly tier-2/tier-3 Indian engineering colleges
(per the master doc's Target Audience section), so a global sample would
dilute salary and skill-demand figures with data irrelevant to that
audience. ConvertedCompYearly is used directly (SO's own USD-normalized
figure) rather than re-deriving from CompTotal/Currency, avoiding a repeat
of the manual salary-parsing work done for the India Jobs dataset.

DevType is tagged to career paths (not filtered) using an exact mapping,
since it's a controlled-vocabulary survey field, not free text - unlike
India Jobs' job titles. Several DevType values (Student, Architect,
management/business roles, QA) are deliberately left untagged: forcing
them into an ill-fitting career path would be a worse error than leaving
them unmapped. Rows with an unmapped DevType are still kept (tag-don't-
filter, same principle as india_jobs_processor.py).
"""

import pandas as pd

COLUMNS_NEEDED = [
    "Country", "DevType", "YearsCode", "WorkExp", "EdLevel",
    "ConvertedCompYearly", "RemoteWork",
    "LanguageHaveWorkedWith", "DatabaseHaveWorkedWith",
    "PlatformHaveWorkedWith", "WebframeHaveWorkedWith",
]

DEVTYPE_TO_CAREER_PATH = {
    "Developer, full-stack": "Software Engineering / Full-Stack Development",
    "Developer, back-end": "Backend / Systems Engineering",
    "Developer, front-end": "UI/UX + Frontend Development",
    "Developer, mobile": "Mobile App Development",
    "AI/ML engineer": "AI / Machine Learning Engineering",
    "Developer, AI apps or physical AI": "AI / Machine Learning Engineering",
    "Data engineer": "Data Science / Data Analytics",
    "Data scientist": "Data Science / Data Analytics",
    "Data or business analyst": "Data Science / Data Analytics",
    "DevOps engineer or professional": "Cloud / DevOps",
    "Cloud infrastructure engineer": "Cloud / DevOps",
    "Developer, embedded applications or devices": "Backend / Systems Engineering",
    "Cybersecurity or InfoSec professional": "Cybersecurity",
    "Developer, game or graphics": "Game Development",
    "UX, Research Ops or UI design professional": "UI/UX + Frontend Development",
    "Academic researcher": "Research / Advanced Computing",
    "Applied scientist": "Research / Advanced Computing",
    "Database administrator or engineer": "Backend / Systems Engineering",
    "System administrator": "Cloud / DevOps",
}
# NOTE: deliberately unmapped - Student, Architect (software or solutions),
# Other, Engineering manager, Senior executive, Founder, Project manager,
# Product manager, Financial analyst or engineer, Support engineer or
# analyst, Developer (QA or test), Retired. Rows with these DevType values
# are kept but get career_path=None.


def _split_skills(raw):
    """Splits a semicolon-delimited skill string into a clean list, or [] if null."""
    if pd.isna(raw):
        return []
    return [s.strip() for s in raw.split(";") if s.strip()]


def process(csv_path, chunksize=50000):
    """
    Reads the full survey CSV in chunks (it's ~140MB - never loaded whole),
    filters to India respondents, and returns a cleaned DataFrame with:
    career_path (str or None), and each skill column split into a list.
    """
    chunk_iter = pd.read_csv(csv_path, usecols=COLUMNS_NEEDED, chunksize=chunksize)
    india_chunks = [chunk[chunk["Country"] == "India"] for chunk in chunk_iter]
    df = pd.concat(india_chunks, ignore_index=True)

    df["career_path"] = df["DevType"].map(DEVTYPE_TO_CAREER_PATH)  # NaN if unmapped

    for col in ["LanguageHaveWorkedWith", "DatabaseHaveWorkedWith",
                "PlatformHaveWorkedWith", "WebframeHaveWorkedWith"]:
        df[col] = df[col].apply(_split_skills)

    return df
