"""
Extracts and cleans roadmap.sh markdown content for the RAG knowledge base.
Reads from a local clone of the roadmap.sh developer-roadmap repo (not committed
to this project — see docs/DEV_SETUP.md for how to fetch it) and produces a
list of {text, career_paths, source, title, node_id, folder, resources}
chunks ready for embedding.

Each content file is `roadmaps/<folder>/content/<slug>@<nodeId>.md` - this is
a content-only mirror of roadmap.sh's database (confirmed via its own
scripts/readme.md), so there is no local JSON graph of node parent/order to
recover; `node_id` is kept only as an opaque identifier back to that file.
Corpus-wide, 0% of ingested files contain H2/H3 headers - each file is
already a single flat leaf topic, not a multi-section document, so there is
no finer-grained sub-chunking to do within a file.
"""

import re
from pathlib import Path

from app.pipeline.career_path_registry import CAREER_PATH_TO_FOLDERS

# Matches roadmap.sh's own resource-link format, e.g.
# "- [@video@ACID Explained](https://www.youtube.com/watch?v=...)"
# (format confirmed against developer-roadmap's own
# formatOfficialRoadmapTopicResourceLink in scripts/lib/official-roadmap-topic.ts).
_RESOURCE_LINE_RE = re.compile(r"^-\s*\[@(\w+)@(.*)\]\((\S+)\)\s*$", re.MULTILINE)
_H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


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


def _extract_title(raw_text, fallback_slug):
    """The node's H1 heading, or the filename slug if the file has none."""
    match = _H1_RE.search(raw_text)
    return match.group(1).strip() if match else fallback_slug


def _extract_resources(raw_text):
    """
    Parses roadmap.sh's "- [@type@Title](url)" resource lines (the block this
    module used to discard) into structured {type, title, url} dicts. A file
    with no resources block returns [].
    """
    return [
        {"type": m.group(1), "title": m.group(2).strip(), "url": m.group(3)}
        for m in _RESOURCE_LINE_RE.finditer(raw_text)
    ]


def extract_chunks(roadmap_sh_root):
    """
    Walk the configured folders under a roadmap.sh clone and return a list of dicts:
    {"text": ..., "career_paths": [...], "source": "folder/file.md",
     "title": ..., "node_id": ..., "folder": ..., "resources": [...]}
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

            # Filenames are always "<slug>@<nodeId>.md" (verified across all
            # 3,599 currently-ingested files - exactly one "@" each).
            slug, node_id = md_file.stem.split("@", 1)

            chunks.append({
                "text": cleaned,
                "career_paths": career_paths,
                "source": f"{folder_name}/{md_file.name}",
                "title": _extract_title(raw_text, fallback_slug=slug),
                "node_id": node_id,
                "folder": folder_name,
                "resources": _extract_resources(raw_text),
            })

    return chunks