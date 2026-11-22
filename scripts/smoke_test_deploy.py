"""
Checks for the settings added for the Render demo (docs/DEPLOY_RENDER.md). Writes nothing to the database.

  - /health answers without touching the database
  - the torch/sentence-transformers stack is not imported by create_app (the memory fix)
  - SEMANTIC_PATH_FIT=false: path-fit never calls the search and still ranks from the survey signal
  - forgot-password: honest "not available" message when no mail is set up (production-like), normal reply when it is
  - DATABASE_URL "postgres://" is rewritten to "postgresql://"
  - TRUST_PROXY_HEADERS: the visitor's address comes from X-Forwarded-For only when it is on

Usage:  PYTHONPATH=. python scripts/smoke_test_deploy.py
"""
import json
import os
import subprocess
import sys

from dotenv import load_dotenv
load_dotenv()

passed = failed = 0


def check(name, ok):
    global passed, failed
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    passed += bool(ok)
    failed += not ok


def child(code, **env):
    """Run `code` in a fresh interpreter (module-level settings are read at import) and return its stdout, or None."""
    merged = dict(os.environ, PYTHONPATH=".", PYTHONIOENCODING="utf-8", **env)
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=merged, timeout=240)
    return done.stdout.strip().splitlines()[-1] if done.returncode == 0 and done.stdout.strip() else None


def main():
    # 1. memory: nothing heavy imported by create_app
    out = child("import sys; from app import create_app; create_app(); "
                "print(json.dumps({m: m in sys.modules for m in ('torch', 'sentence_transformers')}))"
                .replace("json.dumps", "__import__('json').dumps"))
    heavy = json.loads(out) if out else {}
    check("create_app does not import torch", heavy.get("torch") is False)
    check("create_app does not import sentence_transformers", heavy.get("sentence_transformers") is False)

    # 1b. the resume skill extractor loads spaCy without torch, and gives the same skills as before
    out = child("import sys, json; from app.pipeline.resume_skill_extractor import extract_skills; "
                "found = sorted(extract_skills('Built APIs in Python and React, deployed with Docker.', "
                "{'Python', 'React', 'Docker', 'Go'})); "
                "print(json.dumps([found, 'torch' in sys.modules]))")
    found = json.loads(out) if out else [None, None]
    check("resume extraction finds the skills", found[0] == ["Docker", "Python", "React"])
    check("resume extraction does not import torch", found[1] is False)

    # 2. DATABASE_URL scheme
    out = child("from app.config import Config; print(Config.SQLALCHEMY_DATABASE_URI)", DATABASE_URL="postgres://u:p@h:5432/d")
    check("postgres:// is rewritten to postgresql://", out == "postgresql://u:p@h:5432/d")
    out = child("from app.config import Config; print(Config.SQLALCHEMY_DATABASE_URI)", DATABASE_URL="postgresql://u:p@h/d")
    check("postgresql:// is left alone", out == "postgresql://u:p@h/d")

    # 3. proxy headers
    probe = ("from app import create_app\nfrom flask import request\napp = create_app()\n"
             "@app.route('/_ip')\ndef _ip():\n    return request.remote_addr\n"
             "r = app.test_client().get('/_ip', headers={'X-Forwarded-For': '203.0.113.9'}, environ_base={'REMOTE_ADDR': '10.0.0.1'})\n"
             "print(r.get_data(as_text=True))")
    check("proxy headers ignored by default", child(probe, TRUST_PROXY_HEADERS="") == "10.0.0.1")
    check("proxy headers trusted when TRUST_PROXY_HEADERS=true", child(probe, TRUST_PROXY_HEADERS="true") == "203.0.113.9")

    # 4. path-fit without the semantic step
    from app.pipeline import path_fit

    def must_not_run(*args, **kwargs):
        raise AssertionError("search was called")

    skills = {"Python", "Docker", "PostgreSQL", "JavaScript", "React"}
    stats = {"n_overall": 100, "overall": __import__("collections").Counter({s: 20 for s in skills}),
             "paths": {"Backend Engineering": {"n": 50, "counts": __import__("collections").Counter({"Python": 40, "Docker": 30})}}}
    try:
        result = path_fit.fit_for_skills(skills, None, [], stats=stats, search=must_not_run, semantic=False)
        check("semantic=False never calls the search", True)
        check("semantic=False still returns a ranking", isinstance(result, dict) and "list_a" in result)
    except AssertionError:
        check("semantic=False never calls the search", False)
    except Exception as error:      # a stats shape that differs from the real one: report, do not hide
        check(f"semantic=False ranking ran ({type(error).__name__}: {error})", False)
    calls = []
    path_fit.fit_for_skills(skills, None, [], stats=stats, search=lambda *a, **k: calls.append(1) or [], semantic=True)
    check("semantic=True (default) still calls the search", calls == [1])

    # 5. /health and forgot-password, with a production-like app (debug off) and with development
    os.environ["SECRET_KEY"] = "x" * 40
    from app import create_app, mailer
    from app.security import reset_rate_limits
    import re

    for label, name, mail_on, expect_unavailable in (
            ("production, no mail", "production", False, True),
            ("production, mail configured", "production", True, False),
            ("development, no mail (console mode)", "development", False, False)):
        app = create_app(name)
        app.config["MAIL_ASYNC"] = False
        app.config["MAIL_USERNAME"], app.config["MAIL_PASSWORD"] = ("u@example.com", "pw") if mail_on else ("", "")
        reset_rate_limits()
        with app.test_client() as c:
            health = c.get("/health")
            check(f"{label}: /health -> 200 ok", health.status_code == 200 and health.get_json() == {"status": "ok"})
            page = c.get("/login").get_data(as_text=True)
            csrf = re.search(r'<meta name="csrf-token" content="([^"]+)"', page).group(1)
            r = c.post("/forgot-password", json={"email": "nobody-deploy-check@example.com"}, headers={"X-CSRF-Token": csrf})
            if expect_unavailable:
                body = r.get_json() or {}
                check(f"{label}: forgot-password says unavailable (503)", r.status_code == 503 and "not available" in body.get("error", ""))
                check(f"{label}: it does not claim a link was sent", "have sent" not in json.dumps(body))
            else:
                check(f"{label}: forgot-password gives the normal reply (200)",
                      r.status_code == 200 and "we have sent a link" in (r.get_json() or {}).get("message", ""))

    print(f"\n{passed}/{passed + failed} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
