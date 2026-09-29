"""
Rebuilds the FAISS knowledge base index from a fresh extraction of the local
roadmap.sh clone, then re-appends the 10 SO Survey chunks. This reproduces,
as a committed and re-runnable script, the two steps that were previously
done by hand in a REPL session (see docs/PROJECT_BIOGRAPHY.md) - there was
no prior script for either step.

Backs up the current index + metadata to data/processed/backup/ (gitignored)
before overwriting them, so a bad rebuild can be rolled back by hand.

Usage:
    python scripts/rebuild_kb.py [roadmap_sh_root]

roadmap_sh_root defaults to the path below (this machine's local clone -
see docs/DEV_SETUP.md for how to fetch your own; it is not committed here).
"""
import pickle
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import faiss
import numpy as np

from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.config import Config
from app.models import SurveyRespondent
from app.pipeline import rag
from app.pipeline.embedder import embed_chunks
from app.pipeline.so_survey_chunks import generate_survey_chunks

DEFAULT_ROADMAP_SH_ROOT = "C:/developer-roadmap"


def backup_existing_index(index_path):
    index_path = Path(index_path)
    faiss_file = Path(str(index_path) + ".faiss")
    meta_file = Path(str(index_path) + "_meta.pkl")

    if not faiss_file.exists() and not meta_file.exists():
        print("No existing index to back up.")
        return

    backup_dir = index_path.parent / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    for f in (faiss_file, meta_file):
        if f.exists():
            dest = backup_dir / f"{f.name}.{stamp}.bak"
            shutil.copy2(f, dest)
            print(f"Backed up {f} -> {dest}")


def main():
    roadmap_sh_root = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ROADMAP_SH_ROOT
    index_path = Config.FAISS_INDEX_PATH

    backup_existing_index(index_path)

    print(f"Extracting + embedding roadmap.sh chunks from {roadmap_sh_root} ...")
    index, chunks = rag.build_index(roadmap_sh_root, index_path)
    roadmap_chunk_count = len(chunks)
    print(f"Built index with {roadmap_chunk_count} roadmap.sh chunks.")

    app = create_app()
    with app.app_context():
        respondents = SurveyRespondent.query.filter(
            SurveyRespondent.career_path.isnot(None)
        ).all()

    survey_chunks = generate_survey_chunks(respondents)
    print(f"Generated {len(survey_chunks)} SO Survey chunks.")

    survey_embeddings = embed_chunks(survey_chunks)
    norms = np.linalg.norm(survey_embeddings, axis=1, keepdims=True)
    survey_embeddings = (survey_embeddings / norms).astype("float32")

    index.add(survey_embeddings)
    chunks.extend(survey_chunks)

    faiss.write_index(index, str(index_path) + ".faiss")
    with open(str(index_path) + "_meta.pkl", "wb") as f:
        pickle.dump(chunks, f)

    total = len(chunks)
    expected = roadmap_chunk_count + len(survey_chunks)
    assert total == expected, f"chunk count mismatch: {total} != {expected}"
    assert len(survey_chunks) == 10, f"expected 10 survey chunks, got {len(survey_chunks)}"

    print(
        f"Final index: {total} chunks "
        f"({roadmap_chunk_count} roadmap.sh + {len(survey_chunks)} SO Survey)."
    )


if __name__ == "__main__":
    main()
