"""
Smoke test for background roadmap generation: POST /roadmap/generate-async, GET /roadmap/jobs/<id> and the
in-memory registry in app/pipeline/generation_jobs.py. Flask test client with CSRF on. The generator is replaced
by a stub (no LLM, no FAISS index, no network); roadmap rows and test users are deleted at the end.

Usage:
    PYTHONPATH=. python scripts/smoke_test_async_generation.py
"""
import random
import sys
import threading
import time
from unittest.mock import patch

from dotenv import load_dotenv
load_dotenv()

import flask

from app import create_app, db
from app.models import GeneratedRoadmap, User
from app.pipeline import generation_jobs
from scripts._csrf import enable_csrf_client

PASSWORD = "SmokeTest#123"
PATH = "Backend Engineering"
SECRET_DETAIL = "SECRET-EXCEPTION-DETAIL-do-not-leak"
checks = []


def check(description, condition):
    checks.append((description, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {description}")


def fake_roadmap():
    step = {"step_number": 1, "title": "Step", "description": "d", "topic_refs": [], "subtopics": [], "projects": [],
            "more_topics": [], "global_step_index": 1}
    return {"phases": [{"phase_number": 1, "title": "Phase", "steps": [step]}]}, {"phases": []}


class StubGenerator:
    """Replaces generate_roadmap: records where it ran, reports progress, can wait or fail on demand."""
    def __init__(self):
        self.gate = threading.Event()
        self.gate.set()
        self.mode = "ok"
        self.ran = []

    def __call__(self, career_path, signals, index, chunks, on_progress=None, **kw):
        self.ran.append({"thread": threading.current_thread().name, "app_context": flask.has_app_context(),
                         "request_context": flask.has_request_context(), "career_path": career_path})
        if on_progress:
            on_progress(0, 2)
        if not self.gate.wait(10):
            raise RuntimeError("gate never opened")
        if self.mode == "raise":
            raise ValueError(SECRET_DETAIL)
        if self.mode == "exit":
            raise SystemExit(SECRET_DETAIL)
        if on_progress:
            on_progress(1, 2)
            on_progress(2, 2)
        return fake_roadmap()


def wait_for(client, job_id, wanted=("done", "failed"), timeout=10):
    deadline = time.time() + timeout
    seen = []
    while time.time() < deadline:
        resp = client.get(f"/roadmap/jobs/{job_id}")
        body = resp.get_json() or {}
        seen.append(body)
        if body.get("status") in wanted:
            return resp, body, seen
        time.sleep(0.05)
    return resp, body, seen


def wait_idle(user_id, timeout=10):
    """Waits until the user has no queued/running job (so one test step cannot leak into the next)."""
    deadline = time.time() + timeout
    while time.time() < deadline and generation_jobs.active_job_for(user_id) is not None:
        time.sleep(0.05)


def main():
    app = create_app()
    enable_csrf_client(app)
    suffix = random.randint(100000, 999999)
    emails = [f"asynctest{suffix}@example.com", f"asyncother{suffix}@example.com"]
    user_ids = []
    stub = StubGenerator()
    original_limit = app.config["ROADMAP_DAILY_LIMIT"]
    generation_jobs.reset_for_tests()
    try:
        client, other = app.test_client(), app.test_client()
        for c, email in ((client, emails[0]), (other, emails[1])):
            user_ids.append(c.post("/signup", json={"name": "Async Test", "email": email, "password": PASSWORD}).get_json()["user_id"])
        body = {"target_career_path": PATH}

        with patch("app.pipeline.generation_jobs.generate_roadmap", stub), \
                patch("app.routes.roadmap._get_index", lambda: (None, [])):
            check("logged out: generate-async and job status answer 401",
                  client.post("/roadmap/generate-async", json=body).status_code == 401 and client.get("/roadmap/jobs/x").status_code == 401)
            for c, email in ((client, emails[0]), (other, emails[1])):
                c.post("/login", json={"email": email, "password": PASSWORD})

            resp = client.post("/roadmap/generate-async", json=body, headers={"X-CSRF-Token": ""})
            check("CSRF: generate-async without a token -> 400 csrf", resp.status_code == 400 and resp.get_json() == {"error": "csrf"})
            check("validation: an invalid career path -> 400 invalid_career_path (same as /roadmap/generate)",
                  client.post("/roadmap/generate-async", json={"target_career_path": "Nope"}).get_json().get("error") == "invalid_career_path")
            check("validation: no path and no quiz result -> 400 career_path_required",
                  client.post("/roadmap/generate-async", json={}).get_json().get("error") == "career_path_required")

            # 202 and polling to done
            stub.gate.clear()
            resp = client.post("/roadmap/generate-async", json=body)
            job = (resp.get_json() or {}).get("job_id")
            check("start: 202 with a job_id", resp.status_code == 202 and isinstance(job, str) and len(job) >= 16)
            deadline = time.time() + 5
            while not stub.ran and time.time() < deadline:
                time.sleep(0.02)
            running = client.get(f"/roadmap/jobs/{job}").get_json()
            check("polling: a running job reports status, elapsed_s and (from the generator's callback) phase_done/phase_total",
                  running["status"] == "running" and running["elapsed_s"] >= 0 and running["phase_done"] == 0 and running["phase_total"] == 2
                  and "roadmap_id" not in running and "error_code" not in running)

            # second start while running
            resp = client.post("/roadmap/generate-async", json=body)
            check("a second start while one is active -> 409 job_running with the existing job_id",
                  resp.status_code == 409 and resp.get_json() == {"error": "job_running", "job_id": job})

            # ownership
            check("ownership: another user's job id -> 404, an unknown id -> 404",
                  other.get(f"/roadmap/jobs/{job}").status_code == 404 and client.get("/roadmap/jobs/does-not-exist").status_code == 404)
            check("another user is not blocked by this user's active job", other.post("/roadmap/generate-async", json=body).status_code == 202)
            other_job = [j for j, v in generation_jobs._jobs.items() if v["user_id"] == user_ids[1]][0]

            stub.gate.set()
            resp, done, seen = wait_for(client, job)
            check("polling: the job ends done with a roadmap_id and phase counters 2 of 2",
                  done["status"] == "done" and isinstance(done["roadmap_id"], int) and done["phase_done"] == 2 and done["phase_total"] == 2)
            wait_for(other, other_job)
            with app.app_context():
                saved = db.session.get(GeneratedRoadmap, done["roadmap_id"])
                expected_steps, expected_audit = fake_roadmap()
                check("the thread saved the GeneratedRoadmap exactly as the sync route does (user, path, steps, audit)",
                      saved is not None and saved.user_id == user_ids[0] and saved.career_path == PATH
                      and saved.steps == expected_steps and saved.retrieved_chunks == expected_audit)
            check("a finished job can still be read (reload-safe) and the user can start another", client.get(f"/roadmap/jobs/{job}").get_json()["status"] == "done")

            # app context
            run = stub.ran[0]
            check("the worker thread has its own app context and no request context, and is not the main thread",
                  run["app_context"] and not run["request_context"] and run["thread"].startswith("roadmap-job-") and run["thread"] != threading.main_thread().name)

            # failure modes: fixed codes, no exception text, nothing saved
            with app.app_context():
                before = GeneratedRoadmap.query.filter_by(user_id=user_ids[0]).count()
            for mode, code in (("raise", "generation_failed"), ("exit", "unexpected")):
                stub.mode = mode
                resp = client.post("/roadmap/generate-async", json=body)
                _, failed, _ = wait_for(client, resp.get_json()["job_id"])
                check(f"failure ({mode}): the job ends 'failed' with the fixed code '{code}', never stuck running, and no exception text reaches the client",
                      failed["status"] == "failed" and failed["error_code"] == code and SECRET_DETAIL not in str(failed)
                      and "roadmap_id" not in failed)
            stub.mode = "ok"
            with patch("app.pipeline.generation_jobs.GeneratedRoadmap", side_effect=RuntimeError(SECRET_DETAIL)):
                resp = client.post("/roadmap/generate-async", json=body)
                _, failed, _ = wait_for(client, resp.get_json()["job_id"])
            check("failure (save): a database error ends 'failed' with 'save_failed'",
                  failed["status"] == "failed" and failed["error_code"] == "save_failed" and SECRET_DETAIL not in str(failed))
            with app.app_context():
                check("failed jobs saved no roadmap", GeneratedRoadmap.query.filter_by(user_id=user_ids[0]).count() == before)
            with patch.object(threading.Thread, "start", side_effect=RuntimeError(SECRET_DETAIL)):
                resp = client.post("/roadmap/generate-async", json=body)
            status = client.get(f"/roadmap/jobs/{resp.get_json()['job_id']}").get_json()
            check("a thread that cannot start leaves a failed job, not a stuck one, and the user can start again",
                  status["status"] == "failed" and client.post("/roadmap/generate-async", json=body).status_code == 202)
            wait_idle(user_ids[0])

            # daily cap: enforced on start, not consumed by failures
            with app.app_context():
                GeneratedRoadmap.query.filter_by(user_id=user_ids[0]).delete()
                db.session.commit()
            generation_jobs.reset_for_tests()
            app.config["ROADMAP_DAILY_LIMIT"] = 1
            stub.mode = "raise"
            _, failed, _ = wait_for(client, client.post("/roadmap/generate-async", json=body).get_json()["job_id"])
            resp = client.post("/roadmap/generate-async", json=body)
            check("daily cap (limit 1): a FAILED job does not use it up (the next start is accepted, not 429)",
                  failed["status"] == "failed" and resp.status_code == 202)
            wait_idle(user_ids[0])
            stub.mode = "ok"
            resp = client.post("/roadmap/generate-async", json=body)
            _, ok_job, _ = wait_for(client, resp.get_json()["job_id"])
            resp = client.post("/roadmap/generate-async", json=body)
            check("daily cap: after one SUCCESSFUL job the next start -> 429 daily_limit with limit and resets_in_minutes",
                  ok_job["status"] == "done" and resp.status_code == 429 and resp.get_json()["error"] == "daily_limit"
                  and resp.get_json()["limit"] == 1 and resp.get_json()["resets_in_minutes"] >= 1)
            app.config["ROADMAP_DAILY_LIMIT"] = original_limit

            # expiry and the stored-jobs cap
            job_id = next(j for j, v in generation_jobs._jobs.items() if v["status"] == "done")
            generation_jobs._jobs[job_id]["finished"] = time.time() - generation_jobs.JOB_TTL_S - 5
            check("expiry: a job finished more than 1 hour ago is gone (404)", client.get(f"/roadmap/jobs/{job_id}").status_code == 404)
            fresh = {"status": "done", "created": time.time(), "finished": time.time(), "phase_done": None, "phase_total": None,
                     "roadmap_id": 1, "error_code": None}
            generation_jobs.reset_for_tests()
            original_max = generation_jobs.MAX_JOBS
            generation_jobs.MAX_JOBS = 5
            try:
                for i in range(8):
                    generation_jobs._jobs[f"old{i}"] = {**fresh, "user_id": 999, "finished": time.time() - 100 + i}
                generation_jobs.active_job_for(1)
                check("stored-jobs cap: the oldest finished jobs are evicted past MAX_JOBS", len(generation_jobs._jobs) == 5 and "old0" not in generation_jobs._jobs and "old7" in generation_jobs._jobs)
                for i in range(5):
                    generation_jobs._jobs[f"act{i}"] = {**fresh, "user_id": 900 + i, "status": "running", "finished": None}
                for k in [k for k in generation_jobs._jobs if k.startswith("old")]:
                    del generation_jobs._jobs[k]
                resp = client.post("/roadmap/generate-async", json=body)
                check("stored-jobs cap: when the registry is full of ACTIVE jobs a start is refused with 503 busy, not accepted",
                      resp.status_code == 503 and resp.get_json()["error"] == "busy")
            finally:
                generation_jobs.MAX_JOBS = original_max
                generation_jobs.reset_for_tests()

        # the synchronous route is untouched
        with patch("app.routes.roadmap.generate_roadmap", lambda *a, **k: fake_roadmap()), patch("app.routes.roadmap._get_index", lambda: (None, [])):
            with app.app_context():
                GeneratedRoadmap.query.filter_by(user_id=user_ids[0]).delete()
                db.session.commit()
            resp = client.post("/roadmap/generate", json=body)
            data = resp.get_json() or {}
            check("the synchronous /roadmap/generate still returns 201 with its original response keys",
                  resp.status_code == 201 and set(data) == {"roadmap_id", "career_path", "steps", "completed_steps", "completed_count", "total_steps"})
            app.config["ROADMAP_DAILY_LIMIT"] = 1
            resp = client.post("/roadmap/generate", json=body)
            check("the synchronous route's daily cap answer is unchanged (429 daily_limit)", resp.status_code == 429 and resp.get_json()["error"] == "daily_limit")
            app.config["ROADMAP_DAILY_LIMIT"] = original_limit
    finally:
        app.config["ROADMAP_DAILY_LIMIT"] = original_limit
        time.sleep(0.3)
        with app.app_context():
            GeneratedRoadmap.query.filter(GeneratedRoadmap.user_id.in_(user_ids)).delete(synchronize_session=False)
            User.query.filter(User.email.in_(emails)).delete(synchronize_session=False)
            db.session.commit()
        generation_jobs.reset_for_tests()

    passed = sum(1 for _, ok in checks if ok)
    print(f"\n{passed}/{len(checks)} checks passed")
    sys.exit(0 if passed == len(checks) else 1)


if __name__ == "__main__":
    main()
