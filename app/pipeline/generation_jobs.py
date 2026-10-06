"""
Background roadmap generation. A roadmap can take several minutes with a reasoning model, far longer than
a web request should be held open, so POST /roadmap/generate-async starts the same generation in a thread
and the page polls GET /roadmap/jobs/<job_id>.

Design:
- The registry is IN MEMORY (one dict behind one lock): jobs vanish on a restart and are not shared between
  worker processes. That is acceptable for the single-process deployment this app targets (see
  docs/DEV_SETUP.md, Known Issues); a database or Redis table would be the upgrade.
- At most one active (queued or running) job per user. A finished job is kept for JOB_TTL_S (1 hour) so a
  reloaded page can still collect its result; at most MAX_JOBS jobs are stored, oldest finished first.
- The worker thread gets plain data and its own app context (no request or session object). Whatever
  happens inside it, the job ends as "done" or "failed" (a `finally` guarantees it), with a FIXED error
  code; exception text goes to the server log only and never to the client.
- A failed job saves nothing, so it never counts against the daily roadmap cap (which counts saved rows).
- Two modes. "full" is the generation above. "cached" (config ROADMAP_MODE, and a valid reviewed base file exists for the
  path, see app/pipeline/base_roadmaps.py): the base roadmap is copied, personalized by one short LLM call
  (app/pipeline/roadmap_personalizer.py) and saved, which takes seconds. If the personalization fails the base is saved
  without it. The job reports phase_total=1 and "mode" so the page can word its waiting text.
"""
import copy
import logging
import secrets
import threading
import time

from app import db
from app.models import GeneratedRoadmap
from app.pipeline.roadmap_generator import generate_roadmap
from app.pipeline.roadmap_personalizer import personalize

logger = logging.getLogger(__name__)

JOB_TTL_S = 3600
MAX_JOBS = 200

QUEUED, RUNNING, DONE, FAILED = "queued", "running", "done", "failed"
ACTIVE = (QUEUED, RUNNING)

# Fixed codes the client may see (never exception text).
ERROR_GENERATION = "generation_failed"
ERROR_SAVE = "save_failed"
ERROR_UNEXPECTED = "unexpected"

_lock = threading.Lock()
_jobs = {}


def _now():
    return time.time()


def _purge_locked(now):
    """Drop finished jobs older than the TTL; if still over MAX_JOBS, drop the oldest finished ones."""
    for job_id in [j for j, job in _jobs.items() if job["finished"] is not None and now - job["finished"] > JOB_TTL_S]:
        del _jobs[job_id]
    over = len(_jobs) - MAX_JOBS
    if over > 0:
        finished = sorted((job["finished"], j) for j, job in _jobs.items() if job["finished"] is not None)
        for _, job_id in finished[:over]:
            del _jobs[job_id]


def active_job_for(user_id):
    """The user's queued/running job id, or None."""
    with _lock:
        _purge_locked(_now())
        for job_id, job in _jobs.items():
            if job["user_id"] == user_id and job["status"] in ACTIVE:
                return job_id
    return None


def create_job(user_id, mode="full"):
    """
    Registers a new queued job (mode "full" or "cached"; a cached job starts at 0 of 1 parts). Returns (job_id, None), or (None, ("job_running", existing_job_id)) if the
    user already has an active one, or (None, ("busy", None)) if the registry is full of active jobs.
    """
    with _lock:
        now = _now()
        _purge_locked(now)
        for job_id, job in _jobs.items():
            if job["user_id"] == user_id and job["status"] in ACTIVE:
                return None, ("job_running", job_id)
        if len(_jobs) >= MAX_JOBS:
            return None, ("busy", None)
        job_id = secrets.token_urlsafe(16)
        _jobs[job_id] = {"user_id": user_id, "status": QUEUED, "created": now, "finished": None,
                         "phase_done": 0 if mode == "cached" else None, "phase_total": 1 if mode == "cached" else None,
                         "roadmap_id": None, "error_code": None, "mode": mode}
        return job_id, None


def get_status(job_id, user_id):
    """The client-facing status dict, or None if the job is unknown, expired or not this user's."""
    with _lock:
        now = _now()
        _purge_locked(now)
        job = _jobs.get(job_id)
        if job is None or job["user_id"] != user_id:
            return None
        end = job["finished"] if job["finished"] is not None else now
        status = {"status": job["status"], "elapsed_s": round(end - job["created"], 1), "mode": job.get("mode", "full")}
        if job["phase_total"] is not None:
            status["phase_done"] = job["phase_done"]
            status["phase_total"] = job["phase_total"]
        if job["status"] == DONE:
            status["roadmap_id"] = job["roadmap_id"]
        if job["status"] == FAILED:
            status["error_code"] = job["error_code"]
        return status


def _update(job_id, **fields):
    with _lock:
        job = _jobs.get(job_id)
        if job is not None:
            job.update(fields)


def _progress(job_id):
    def on_progress(done, total):
        _update(job_id, phase_done=done, phase_total=total)
    return on_progress


def _cached_steps(career_path, conversation_signals, base):
    """The base roadmap (already a private copy) with the personalization, if it succeeded, and a "base" marker."""
    steps = base["roadmap"]
    try:
        personalization = personalize(career_path, conversation_signals, steps)
    except Exception:
        logger.exception("personalization crashed; saving the base roadmap without it")
        personalization = None
    if personalization:
        steps["personalization"] = personalization
    meta = base["metadata"]
    steps["base"] = {"source": "base_roadmap", "model_id": meta.get("model_id"), "built_at": meta.get("built_at"),
                     "stale": bool(base.get("stale"))}
    return steps, copy.deepcopy(base["audit"])


def _run(app, job_id, user_id, career_path, conversation_signals, index, chunks, base=None):
    """Thread body. Never raises; always leaves the job done or failed."""
    outcome = {"status": FAILED, "error_code": ERROR_UNEXPECTED, "roadmap_id": None}
    try:
        _update(job_id, status=RUNNING)
        with app.app_context():
            try:
                if base is None:
                    steps, audit = generate_roadmap(career_path, conversation_signals, index, chunks,
                                                    on_progress=_progress(job_id))
                else:
                    steps, audit = _cached_steps(career_path, conversation_signals, base)
                    _update(job_id, phase_done=1, phase_total=1)
            except Exception:
                logger.exception("roadmap job %s: generation failed", job_id)
                outcome["error_code"] = ERROR_GENERATION
                return
            try:
                roadmap = GeneratedRoadmap(user_id=user_id, career_path=career_path, steps=steps, retrieved_chunks=audit)
                db.session.add(roadmap)
                db.session.commit()
                outcome.update(status=DONE, error_code=None, roadmap_id=roadmap.id)
            except Exception:
                logger.exception("roadmap job %s: saving failed", job_id)
                db.session.rollback()
                outcome["error_code"] = ERROR_SAVE
            finally:
                db.session.remove()
    except BaseException:
        logger.exception("roadmap job %s: crashed", job_id)
        outcome.update(status=FAILED, error_code=ERROR_UNEXPECTED, roadmap_id=None)
    finally:
        _update(job_id, status=outcome["status"], error_code=outcome["error_code"],
                roadmap_id=outcome["roadmap_id"], finished=_now())


def start_job(app, job_id, user_id, career_path, conversation_signals, index, chunks, base=None):
    """Starts the worker thread for a job created with create_job (base: a loaded base roadmap for a cached job)."""
    thread = threading.Thread(target=_run, name=f"roadmap-job-{job_id[:6]}", daemon=True,
                              args=(app, job_id, user_id, career_path, conversation_signals, index, chunks, base))
    try:
        thread.start()
    except Exception:
        logger.exception("roadmap job %s: could not start its thread", job_id)
        _update(job_id, status=FAILED, error_code=ERROR_UNEXPECTED, finished=_now())
        return None
    return thread


def reset_for_tests():
    with _lock:
        _jobs.clear()
