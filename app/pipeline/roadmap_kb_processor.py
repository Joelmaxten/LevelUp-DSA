"""
Extracts and cleans roadmap.sh markdown content for the RAG knowledge base.
Reads from a local clone of the roadmap.sh developer-roadmap repo (not committed
to this project — see docs/DEV_SETUP.md for how to fetch it) and produces a
list of {text, career_paths, source_folder} chunks ready for embedding.
"""

import re
from pathlib import Path

# Maps each of the quiz's 10 career paths to the roadmap.sh folders that feed it.
# A folder can appear under more than one career path (e.g. "sql" is relevant to
# both Data Science and Backend).
CAREER_PATH_TO_FOLDERS = {
    "Software Engineering / Full-Stack Development": ["full-stack", "javascript", "react", "nodejs", "git-github"],
    "AI / Machine Learning Engineering": ["machine-learning", "ai-engineer", "python"],
    "Data Science / Data Analytics": ["data-analyst", "python-data-analysis", "sql"],
    "Cybersecurity": ["cyber-security", "devsecops"],
    "Cloud / DevOps": ["devops", "aws", "docker", "kubernetes"],
    "Mobile App Development": ["android", "ios", "react-native"],
    "Game Development": ["game-developer", "cpp"],
    "UI/UX + Frontend Development": ["frontend", "ux-design", "css"],
    "Backend / Systems Engineering": ["backend", "sql", "system-design"],
    "Research / Advanced Computing": ["computer-science", "datastructures-and-algorithms"],
}


def _clean_markdown(raw_text):
    """Strip roadmap.sh's markdown formatting down to plain descriptive text."""
    text = raw_text

    # Remove the "Visit the following resources to learn more:" line and everything after it —
    # that's just a resource link list, not descriptive content useful for semantic search.
    text = re.split(r"Visit the following resources", text)[0]

    # Remove markdown headers (# React -> React)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)

    # Collapse extra whitespace/newlines
    text = re.sub(r"\n+", " ", text).strip()

    return text


def _folder_to_career_paths(folder_name):
    """Reverse-lookup: given a roadmap.sh folder name, which career path(s) use it?"""
    return [
        path for path, folders in CAREER_PATH_TO_FOLDERS.items()
        if folder_name in folders
    ]


def extract_chunks(roadmap_sh_root):
    """
    Walk the configured folders under a roadmap.sh clone and return a list of dicts:
    {"text": ..., "career_paths": [...], "source": "folder/file.md"}
    """
    roadmap_sh_root = Path(roadmap_sh_root)
    chunks = []

    all_folders = {folder for folders in CAREER_PATH_TO_FOLDERS.values() for folder in folders}

    for folder_name in sorted(all_folders):
        content_dir = roadmap_sh_root / "roadmaps" / folder_name / "content"
        if not content_dir.exists():
            print(f"WARNING: folder not found, skipping: {folder_name}")
            continue

        career_paths = _folder_to_career_paths(folder_name)

        for md_file in content_dir.glob("*.md"):
            raw_text = md_file.read_text(encoding="utf-8")
            cleaned = _clean_markdown(raw_text)

            if len(cleaned) < 20:
                continue  # skip near-empty files, not useful as embeddings

            chunks.append({
                "text": cleaned,
                "career_paths": career_paths,
                "source": f"{folder_name}/{md_file.name}",
            })

    return chunks