"""
How the cross-phase duplicate threshold (config.DUPLICATE_SIMILARITY_THRESHOLD) was chosen.

Takes the saved REAL roadmaps in scratch/roadmap_*.json (made by scripts/inspect_roadmap.py
against a real model), embeds every step title with the same local model the generator
uses, and for each candidate threshold counts how many cross-phase step pairs it would flag.
A flagged pair is a false positive unless it is in KNOWN_DUPLICATES - pairs a person judged
to be the same step written twice. It also scores a small set of hand-written paraphrase
pairs ("Introduction to Git" / "Git Basics") to estimate how many real duplicates a
threshold catches. Local only: no LLM, no network.

Usage:
    PYTHONPATH=. python scripts/measure_duplicate_threshold.py
"""
import glob
import itertools
import json

import numpy as np
from dotenv import load_dotenv
load_dotenv()

from app.pipeline.embedder import embed_chunks
from app.pipeline.roadmap_generator import _normalise_title

THRESHOLDS = (0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90)

# Pairs from the saved real roadmaps that a person judged to be the same step written twice.
KNOWN_DUPLICATES = {
    frozenset({"Local Storage and Data Persistence", "Data Persistence and Local Storage"}),   # Mobile App Development
}

PARAPHRASES = [
    ("Introduction to Git", "Git Basics"), ("Python Fundamentals", "Python Basics for Beginners"),
    ("Docker Containers Basics", "Introduction to Docker"), ("SQL Fundamentals", "Learning SQL Basics"),
    ("REST API Design", "Designing RESTful APIs"), ("Linux Command Line Essentials", "Command Line Basics on Linux"),
    ("State Management in React", "Managing State in React Applications"), ("Unit Testing Fundamentals", "Writing Unit Tests"),
    ("Network Security Basics", "Fundamentals of Network Security"), ("Object-Oriented Programming", "OOP Concepts and Principles"),
    ("Machine Learning Model Evaluation", "Evaluating ML Models"), ("CI/CD Pipelines", "Continuous Integration and Delivery Pipelines"),
]


def unit_embeddings(titles):
    emb = embed_chunks([{"text": t} for t in titles], show_progress=False)
    return emb / np.linalg.norm(emb, axis=1, keepdims=True)


def main():
    pairs = []
    n_roadmaps = n_steps = 0
    for path in sorted(glob.glob("scratch/roadmap_*.json")):
        data = json.load(open(path, encoding="utf-8"))
        roadmap = data.get("roadmap")
        if not roadmap or "phases" not in roadmap:
            continue
        steps = [(ph["phase_number"], s["title"]) for ph in roadmap["phases"] for s in ph["steps"]]
        n_roadmaps += 1
        n_steps += len(steps)
        emb = unit_embeddings([t for _, t in steps])
        sim = emb @ emb.T
        for i, j in itertools.combinations(range(len(steps)), 2):
            if steps[i][0] != steps[j][0]:
                exact = _normalise_title(steps[i][1]) == _normalise_title(steps[j][1])
                pairs.append((1.0 if exact else float(sim[i, j]), data["career_path"], steps[i][1], steps[j][1]))

    pairs.sort(key=lambda p: -p[0])
    print(f"{n_roadmaps} real roadmaps, {n_steps} steps, {len(pairs)} cross-phase pairs\n")
    print("Most similar cross-phase pairs:")
    for sim, path, a, b in pairs[:10]:
        mark = "  <- judged a true duplicate" if frozenset({a, b}) in KNOWN_DUPLICATES else ""
        print(f"  {sim:.3f}  {path[:22]:<22} {a[:44]:<44} | {b[:44]}{mark}")

    para_sims = []
    for a, b in PARAPHRASES:
        e = unit_embeddings([a, b])
        para_sims.append(float(e[0] @ e[1]))

    print(f"\n{'threshold':>9} {'flagged':>8} {'false pos.':>10} {'FP rate':>9} {'paraphrases caught':>20}")
    for t in THRESHOLDS:
        flagged = [p for p in pairs if p[0] >= t]
        false_pos = [p for p in flagged if frozenset({p[2], p[3]}) not in KNOWN_DUPLICATES]
        caught = sum(1 for s in para_sims if s >= t)
        print(f"{t:>9.2f} {len(flagged):>8} {len(false_pos):>10} {len(false_pos) / len(pairs):>8.2%} {caught:>10} of {len(PARAPHRASES)}")


if __name__ == "__main__":
    main()
