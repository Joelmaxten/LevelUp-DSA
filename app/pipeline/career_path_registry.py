"""
Single source of truth for the 15 career paths and which roadmap.sh
knowledge-base folders ground each one. Every other module that needs the
list of paths or the path->folders mapping imports it from here instead of
holding its own copy - see docs/PROJECT_BIOGRAPHY.md's "Career Path
Restructuring" entry for how these 15 replaced the old 10, and why (AI/ML,
Data Science/Analytics, UI/UX+Frontend and Cloud/DevOps split; Full-Stack
and Backend renamed; QA & Test Automation and Data Engineering added;
Research / Advanced Computing removed entirely - it is not carried forward
in any form).

Order matters here: it's the order paths are offered in the standalone
career-path picker (resolve_target_career_path) and iterated when seeding
CareerPath rows (scripts/seed_dsa.py).
"""

FULL_STACK = "Full-Stack Development"

CAREER_PATH_REGISTRY = [
    {"name": "Full-Stack Development", "folders": ["full-stack", "javascript", "react", "nodejs", "git-github"]},
    {"name": "AI Engineering", "folders": ["ai-engineer", "ai-agents", "prompt-engineering", "ai-red-teaming", "python"]},
    {"name": "Machine Learning Engineering", "folders": ["machine-learning", "mlops", "python"]},
    {"name": "Data Science", "folders": ["python-data-analysis", "sql", "ai-data-scientist", "machine-learning"]},
    {"name": "Data Analytics", "folders": ["data-analyst", "bi-analyst", "power-bi", "sql"]},
    {"name": "Cybersecurity", "folders": ["cyber-security", "devsecops"]},
    {"name": "Mobile App Development", "folders": ["android", "ios", "react-native"]},
    {"name": "Game Development", "folders": ["game-developer", "cpp"]},
    {"name": "Backend Engineering", "folders": ["backend", "sql", "system-design"]},
    {"name": "UI/UX Design", "folders": ["ux-design", "design-system", "product-design"]},
    {"name": "Frontend Development", "folders": ["frontend", "html", "css", "javascript", "typescript", "react", "nextjs"]},
    {"name": "Cloud Engineering", "folders": ["aws", "docker", "kubernetes", "terraform"]},
    {"name": "DevOps", "folders": ["devops", "docker", "kubernetes", "linux"]},
    {"name": "QA & Test Automation", "folders": ["python", "sql", "git-github", "api-design", "qa"]},
    {"name": "Data Engineering", "folders": ["data-engineer", "sql", "python"]},
]

CAREER_PATHS = [entry["name"] for entry in CAREER_PATH_REGISTRY]

CAREER_PATH_TO_FOLDERS = {entry["name"]: entry["folders"] for entry in CAREER_PATH_REGISTRY}
