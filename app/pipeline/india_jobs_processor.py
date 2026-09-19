"""
Processes the India Job Market & Salary dataset (Kaggle) into clean,
structured rows ready for PostgreSQL. Per the master doc's "What Goes
Where" spec and the later scope correction (tag, don't discard, since
career paths will expand beyond today's 10): every row is kept, salary is
parsed and sanity-checked, and career-path relevance is tagged rather than
filtered - untagged rows just mean no match against today's 10 paths, not
that the row was judged irrelevant.
"""

import re

import pandas as pd

SALARY_CEILING = 1800000  # ₹18L/year - above this, flag rather than trust blindly;
                           # this dataset skews entry-level/fresher, so higher figures
                           # are more likely a source mislabeling (e.g. month vs year)
                           # than a real senior salary.

CAREER_PATH_KEYWORDS = {
    "Software Engineering / Full-Stack Development": [
        "full stack", "full-stack", "react", "node", "javascript", "js developer",
        "web developer", "frontend developer", "front end developer", "front-end developer",
        "backend developer", "php developer", "mern stack", "software engineer",
        "software developer", "programmer", "application developer",
    ],
    "AI / Machine Learning Engineering": [
        "machine learning", "ml engineer", "ai engineer", "ai developer",
        "deep learning", "nlp engineer",
    ],
    "Data Science / Data Analytics": [
        "data scientist", "data analyst", "data analytics", "business analyst",
    ],
    "Cybersecurity": [
        "cyber security", "cybersecurity", "security analyst",
        "penetration test", "soc analyst", "network security",
    ],
    "Cloud / DevOps": [
        "devops", "cloud engineer", "cloud support", "aws", "azure",
        "kubernetes", "site reliability",
    ],
    "Mobile App Development": [
        "android developer", "ios developer", "mobile developer",
        "mobile app developer", "react native", "flutter",
    ],
    "Game Development": ["game developer", "unity developer", "unreal"],
    "UI/UX + Frontend Development": ["ui/ux", "ui developer", "ux designer", "ui designer"],
    "Backend / Systems Engineering": [
        "backend developer", "system engineer", "system analyst",
        "java developer", "python developer", ".net developer", "database administrator",
    ],
    "Research / Advanced Computing": ["research engineer", "research scientist"],
}
# NOTE: QA/Testing roles (QA Engineer, Quality Analyst, Software Tester) appear
# frequently in this dataset but have no matching career path in the quiz's
# current 10 CAREER_PATHS - deliberately left untagged rather than force-fit
# into an ill-fitting bucket. Revisit if a QA/Testing path is ever added.


def parse_salary(salary_str):
    """
    Extracts an estimated annual salary from a free-text salary string, or
    None if it can't be reliably parsed. Never invents a range from a
    one-sided figure ("From X", "Up to X") or annualizes hourly/daily rates
    (no defensible working-days/hours assumption is present in the source).
    """
    if pd.isna(salary_str) or salary_str == "Not specified":
        return None

    lower = salary_str.lower()

    if "a day" in lower or "an hour" in lower:
        return None
    if "from" in lower or "up to" in lower:
        return None
    if "year" not in lower and "month" not in lower:
        return None

    numbers = re.findall(r"[\d,]+\.?\d*", salary_str)
    if not numbers:
        return None
    numbers = [float(n.replace(",", "")) for n in numbers]

    midpoint = (numbers[0] + numbers[1]) / 2 if len(numbers) >= 2 else numbers[0]

    return midpoint if "year" in lower else midpoint * 12


def tag_career_paths(title):
    """Returns the list of career paths (from today's 10) this title matches, if any."""
    title_lower = title.lower()
    return [
        path for path, keywords in CAREER_PATH_KEYWORDS.items()
        if any(kw in title_lower for kw in keywords)
    ]


def process(csv_path):
    """
    Loads and processes the raw India Jobs CSV into a clean DataFrame with:
    annual_salary (float or None), salary_suspicious (bool), career_paths (list).
    Does not drop any rows - every row from the source survives, per the
    tag-don't-filter design decision.
    """
    df = pd.read_csv(csv_path)

    df["annual_salary"] = df["Salary"].apply(parse_salary)
    df["salary_suspicious"] = df["annual_salary"] > SALARY_CEILING
    df["career_paths"] = df["Job Title"].apply(tag_career_paths)

    return df