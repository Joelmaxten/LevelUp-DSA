"""
FAISS-backed retrieval for the RAG pipeline. Builds a vector index from
knowledge base chunks, persists it to disk, and provides semantic search
over it (cosine similarity, matching the master doc's spec).
"""

import pickle
from pathlib import Path

import faiss
import numpy as np

from app.pipeline.roadmap_kb_processor import extract_chunks
from app.pipeline.embedder import embed_chunks, get_model


def _normalize(embeddings):
    """L2-normalize vectors so inner product search behaves as cosine similarity."""
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    return embeddings / norms


def build_index(roadmap_sh_root, index_path):
    """
    Full pipeline: extract chunks -> embed -> build a FAISS index -> save to disk.
    Also saves the chunk metadata (text/career_paths/source) alongside the index,
    since FAISS itself only stores vectors, not the original text.
    """
    index_path = Path(index_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)

    chunks = extract_chunks(roadmap_sh_root)
    embeddings = embed_chunks(chunks)
    embeddings = _normalize(embeddings).astype("float32")

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)  # inner product on normalized vectors = cosine similarity
    index.add(embeddings)

    faiss.write_index(index, str(index_path) + ".faiss")
    with open(str(index_path) + "_meta.pkl", "wb") as f:
        pickle.dump(chunks, f)

    return index, chunks


def load_index(index_path):
    """Load a previously-built FAISS index and its chunk metadata from disk."""
    index = faiss.read_index(str(index_path) + ".faiss")
    with open(str(index_path) + "_meta.pkl", "rb") as f:
        chunks = pickle.load(f)
    return index, chunks


def search(query_text, index, chunks, top_k=5, career_path=None):
    """
    Semantic search: embed the query, find the top-K most similar chunks.
    If career_path is given, only chunks tagged with that career path are considered.
    """
    model = get_model()
    query_embedding = model.encode([query_text], convert_to_numpy=True)
    query_embedding = _normalize(query_embedding).astype("float32")

    # Search more than top_k initially, in case we need to filter by career_path after
    search_k = top_k * 10 if career_path else top_k
    scores, indices = index.search(query_embedding, search_k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:
            continue
        chunk = chunks[idx]
        if career_path and career_path not in chunk["career_paths"]:
            continue
        results.append({**chunk, "score": float(score)})
        if len(results) >= top_k:
            break

    return results


def search_diverse(queries, index, chunks, career_path, total_k=30, per_folder_cap=6):
    """
    Multi-query retrieval for callers that want breadth across a career path
    rather than one narrow query's nearest neighbors. Runs each query in
    `queries` against the index (filtered to `career_path`), merges results
    keeping each source's single best score across all queries, then walks
    the merged ranking applying `per_folder_cap` (so one big roadmap.sh
    folder like cyber-security can't crowd out the rest) until `total_k`
    chunks are collected. Same dict shape as search() (chunk fields + "score").

    Does not change search()'s behavior or signature - this is additive.
    """
    model = get_model()
    query_embeddings = model.encode(list(queries), convert_to_numpy=True)
    query_embeddings = _normalize(query_embeddings).astype("float32")

    search_k = total_k * 10
    best_by_source = {}

    for query_embedding in query_embeddings:
        scores, indices = index.search(query_embedding.reshape(1, -1), search_k)
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            chunk = chunks[idx]
            if career_path not in chunk["career_paths"]:
                continue
            source = chunk["source"]
            score = float(score)
            if source not in best_by_source or score > best_by_source[source][0]:
                best_by_source[source] = (score, chunk)

    ranked = sorted(best_by_source.values(), key=lambda pair: pair[0], reverse=True)

    results = []
    folder_counts = {}
    for score, chunk in ranked:
        folder = chunk.get("folder") or chunk["source"].split("/", 1)[0]
        if folder_counts.get(folder, 0) >= per_folder_cap:
            continue
        results.append({**chunk, "score": score})
        folder_counts[folder] = folder_counts.get(folder, 0) + 1
        if len(results) >= total_k:
            break

    return results


def list_topics(career_path, chunks):
    """
    Every KB topic tagged with `career_path`, as [{title, source, folder}] -
    for browsing what a career path's chunks actually cover, independent of
    any query. Excludes the SO Survey chunks (they're per-path aggregate
    stats, not individual topics, and predate the title/folder fields).
    """
    return [
        {"title": chunk["title"], "source": chunk["source"], "folder": chunk["folder"]}
        for chunk in chunks
        if career_path in chunk["career_paths"] and not chunk["source"].startswith("so_survey")
    ]