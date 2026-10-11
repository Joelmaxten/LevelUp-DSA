"""
Code-execution adapter for graded Python questions. One function, run_batch(source, stdins), hides the provider.

Providers (config CODE_RUNNER): "onecompiler" (real HTTP call) or "fake" (executes nothing, returns scripted
results; for tests and offline demos). Each result is {"stdout": str, "stderr": str, "exception": None | "time_limit"
| "memory_limit" | "error"}. The provider's own text is never passed on except what the student's program printed
(stdout/stderr), and it never appears in a CodeRunnerError, a log line or a response. The API key is read from
ONECOMPILER_API_KEY (config) and is only ever sent as a request header.

Errors are always CodeRunnerError with one fixed code: timeout, runtime_error, runner_unavailable, code_too_large.
"""
import os

import requests

CODES = ("timeout", "runtime_error", "runner_unavailable", "code_too_large")

MAX_SOURCE_BYTES = 8 * 1024
MAX_STDINS = 10
MAX_STDIN_BYTES = 2 * 1024
MAX_OUTPUT_CHARS = 20000       # per stream kept from the provider; routes truncate further for the browser
REQUEST_TIMEOUT_S = 15

ONECOMPILER_URL = "https://api.onecompiler.com/v1/run"
# A browser-style User-Agent is required: the default python-requests one is answered by Cloudflare with a 403 page.
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/124.0.0.0 Safari/537.36")


class CodeRunnerError(Exception):
    """Carries only a fixed code; str(error) is the code."""

    def __init__(self, code):
        assert code in CODES
        super().__init__(code)
        self.code = code


# ---------------------------------------------------------------- settings
def _setting(name, default=""):
    try:
        from flask import current_app, has_app_context
        if has_app_context() and name in current_app.config:
            return current_app.config[name]
    except Exception:
        pass
    return os.environ.get(name, default)


def runner_name():
    name = str(_setting("CODE_RUNNER", "onecompiler") or "onecompiler").strip().lower()
    return name if name in ("onecompiler", "fake") else "onecompiler"


def api_key_variable():
    """The NAME of the environment variable that holds the key (for messages); never its value."""
    return "ONECOMPILER_API_KEY"


# ---------------------------------------------------------------- fake runner
_fake = None


def set_fake_runner(script):
    """For tests and demos. script: a callable (source, stdins) -> list of results (it may raise CodeRunnerError),
    or a fixed list of results returned as is. None restores the default fake (every run prints nothing)."""
    global _fake
    _fake = script


def _run_fake(source, stdins):
    if _fake is None:
        return [{"stdout": "", "stderr": "", "exception": None} for _ in stdins]
    results = _fake(source, list(stdins)) if callable(_fake) else list(_fake)
    return [_clean(r) for r in results]


# ---------------------------------------------------------------- shared helpers
def _check_caps(source, stdins):
    if not isinstance(source, str) or not isinstance(stdins, (list, tuple)) or not all(isinstance(s, str) for s in stdins):
        raise CodeRunnerError("runtime_error")
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES or len(stdins) > MAX_STDINS:
        raise CodeRunnerError("code_too_large")
    if any(len(s.encode("utf-8")) > MAX_STDIN_BYTES for s in stdins):
        raise CodeRunnerError("code_too_large")


def _text(value):
    return value[:MAX_OUTPUT_CHARS] if isinstance(value, str) else ""


def _exception_kind(value):
    """Provider exception text -> a fixed token, so provider wording never travels further."""
    if not value:
        return None
    low = str(value).lower()
    if "time" in low:
        return "time_limit"
    if "memory" in low:
        return "memory_limit"
    return "error"


def _clean(item):
    if not isinstance(item, dict):
        raise CodeRunnerError("runtime_error")
    return {"stdout": _text(item.get("stdout")), "stderr": _text(item.get("stderr")),
            "exception": _exception_kind(item.get("exception"))}


# ---------------------------------------------------------------- OneCompiler
def _post_once(source, stdins, key):
    body = {"language": "python", "stdin": list(stdins), "files": [{"name": "main.py", "content": source}]}
    headers = {"X-API-Key": key, "User-Agent": USER_AGENT, "Accept": "application/json",
               "Content-Type": "application/json"}
    return requests.post(ONECOMPILER_URL, json=body, headers=headers, timeout=REQUEST_TIMEOUT_S)


def _run_onecompiler(source, stdins):
    key = str(_setting("ONECOMPILER_API_KEY", "") or "").strip()
    if not key:
        raise CodeRunnerError("runner_unavailable")
    response = None
    for attempt in (1, 2):          # one retry, only for a connection error
        try:
            response = _post_once(source, stdins, key)
            break
        except requests.Timeout:    # includes ConnectTimeout; never retried
            raise CodeRunnerError("timeout") from None
        except requests.ConnectionError:
            if attempt == 2:
                raise CodeRunnerError("runner_unavailable") from None
        except requests.RequestException:
            raise CodeRunnerError("runner_unavailable") from None
    if response is None or response.status_code != 200:
        raise CodeRunnerError("runner_unavailable")
    try:
        payload = response.json()
    except ValueError:              # e.g. a Cloudflare HTML page
        raise CodeRunnerError("runner_unavailable") from None
    if isinstance(payload, dict) and len(stdins) == 1:
        payload = [payload]         # a single result object is accepted when only one input was sent
    if not isinstance(payload, list) or len(payload) != len(stdins):
        raise CodeRunnerError("runner_unavailable")
    return [_clean(item) for item in payload]


# ---------------------------------------------------------------- public entry point
def run_batch(source, stdins):
    """Run `source` once per entry of `stdins` in ONE provider call (one credit). Returns one result per stdin."""
    _check_caps(source, stdins)
    if not stdins:
        return []
    results = _run_fake(source, stdins) if runner_name() == "fake" else _run_onecompiler(source, stdins)
    if len(results) != len(stdins):
        raise CodeRunnerError("runner_unavailable")
    return results
