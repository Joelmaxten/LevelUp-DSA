"""
Generates sentence embeddings for knowledge base text chunks using
sentence-transformers (all-MiniLM-L6-v2, 384 dimensions).
"""

from sentence_transformers import SentenceTransformer

_model = None


def get_model():
    """Load the embedding model once and reuse it (loading is slow, encoding is fast)."""
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed_chunks(chunks, batch_size=32, show_progress=True):
    """
    Takes a list of {"text": ..., "career_paths": ..., "source": ...} dicts
    (as produced by roadmap_kb_processor.extract_chunks, or
    so_survey_chunks.generate_survey_chunks) and returns a numpy array of
    shape (len(chunks), 384) — one embedding per chunk, in the same order
    as the input.

    The stored "text" field stays clean prose either way; when a chunk also
    carries a "title" (roadmap.sh chunks do, survey chunks don't), the title
    is prepended for embedding only, so retrieval benefits from the node's
    own name without duplicating it into the stored/displayed text.
    """
    model = get_model()
    texts = [
        f"{chunk['title']}. {chunk['text']}" if chunk.get("title") else chunk["text"]
        for chunk in chunks
    ]

    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=show_progress,
        convert_to_numpy=True,
    )

    return embeddings