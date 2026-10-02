"""
Background warm-up of the two slow-to-load pieces roadmap generation needs: the
sentence-transformer model (about 20 s the first time in a process) and the
FAISS index plus chunk metadata. Called from run.py when the server starts,
never from create_app(), so tests, scripts and the dev reloader's watcher
process (which never serves a request) don't pay for it.

Safe by construction: a daemon thread (never blocks shutdown), every step wrapped
so a failure is logged and swallowed (a request would simply load things itself,
as before), and the loaders it calls are lock-protected so a request arriving
mid-warm-up waits for the one load instead of starting a second.
"""
import logging
import threading
import time

from app.config import Config

logger = logging.getLogger(__name__)

_started = False
_start_lock = threading.Lock()


def _warm():
    started = time.perf_counter()
    try:
        from app.pipeline.embedder import embed_chunks, get_model
        get_model()
        embed_chunks([{"text": "warm up"}], show_progress=False)   # first encode has its own one-time cost
        logger.info("warmup embedding_model seconds=%.2f", time.perf_counter() - started)
    except Exception:
        logger.exception("warmup of the embedding model failed (it will load on first use instead)")
    started = time.perf_counter()
    try:
        from app.routes.roadmap import _get_index
        _get_index()
        logger.info("warmup faiss_index seconds=%.2f", time.perf_counter() - started)
    except FileNotFoundError:
        logger.warning("warmup: FAISS index not found; roadmap generation will report it as unavailable")
    except Exception:
        logger.exception("warmup of the FAISS index failed (it will load on first use instead)")


def start_warmup():
    """Start the warm-up thread once per process. Returns the thread, or None if disabled/already started."""
    global _started
    if not Config.WARMUP_ON_START:
        return None
    with _start_lock:
        if _started:
            return None
        _started = True
    thread = threading.Thread(target=_warm, name="warmup", daemon=True)
    thread.start()
    return thread
