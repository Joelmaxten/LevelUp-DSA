"""
Code-execution adapter for graded code questions. One function, run_batch(source, stdins, language), hides the
provider. Languages (LANGUAGES): python, cpp, java, javascript. The tests are stdin -> stdout, so every problem works in
every language unchanged; only the file name and the provider's language id differ.

Providers (config CODE_RUNNER): "onecompiler" (real HTTP call), "fake" (executes nothing, returns scripted
results; for tests) or "local" (runs the code with this machine's toolchains in a subprocess with a time limit, for an
OFFLINE DEMO ON YOUR OWN LAPTOP ONLY: it is not a sandbox, so never enable it on a server other people can reach; only
languages whose toolchain is installed are offered, see available_languages()). Each result is {"stdout": str, "stderr": str, "exception": None | "time_limit"
| "memory_limit" | "error"}. The provider's own text is never passed on except what the student's program printed
(stdout/stderr), and it never appears in a CodeRunnerError, a log line or a response. The API key is read from
ONECOMPILER_API_KEY (config) and is only ever sent as a request header.

Errors are always CodeRunnerError with one fixed code: timeout, runtime_error, runner_unavailable, code_too_large.
"""
import inspect
import os
import shutil
import subprocess
import sys
import tempfile

import requests

CODES = ("timeout", "runtime_error", "runner_unavailable", "code_too_large")

MAX_SOURCE_BYTES = 8 * 1024
MAX_STDINS = 10
MAX_STDIN_BYTES = 2 * 1024
MAX_OUTPUT_CHARS = 20000       # per stream kept from the provider; routes truncate further for the browser
REQUEST_TIMEOUT_S = 15

# The allowlist. "onecompiler" is the provider's language id (from its API docs: python, cpp, java, nodejs; "nodejs"
# rather than "javascript" because the program reads stdin), "file" the file the source is sent as (Java needs the
# public class Main in Main.java), "label" what the student sees.
LANGUAGES = {
    "python": {"label": "Python 3", "onecompiler": "python", "file": "main.py"},
    "cpp": {"label": "C++17", "onecompiler": "cpp", "file": "main.cpp"},
    "java": {"label": "Java", "onecompiler": "java", "file": "Main.java"},
    "javascript": {"label": "JavaScript (Node.js)", "onecompiler": "nodejs", "file": "index.js"},
}
DEFAULT_LANGUAGE = "python"

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
    return name if name in ("onecompiler", "fake", "local") else "onecompiler"


def _local_tools():
    """language -> the toolchain programs it needs on PATH (python always uses this interpreter)."""
    return {"cpp": ("g++",), "java": ("javac", "java"), "javascript": ("node",)}


def available_languages():
    """The languages this runner can run now, in LANGUAGES order. "local" offers only installed toolchains."""
    if runner_name() != "local":
        return list(LANGUAGES)
    tools = _local_tools()
    return [lang for lang in LANGUAGES
            if lang == "python" or all(shutil.which(t) for t in tools.get(lang, ()))]


def api_key_variable():
    """The NAME of the environment variable that holds the key (for messages); never its value."""
    return "ONECOMPILER_API_KEY"


# ---------------------------------------------------------------- fake runner
_fake = None


def set_fake_runner(script):
    """For tests and demos. script: a callable (source, stdins) or (source, stdins, language) -> list of results (it
    may raise CodeRunnerError), or a fixed list of results returned as is. None restores the default fake (every run
    prints nothing)."""
    global _fake
    _fake = script


def _run_fake(source, stdins, language):
    if _fake is None:
        return [{"stdout": "", "stderr": "", "exception": None} for _ in stdins]
    if callable(_fake):
        try:
            takes_language = len(inspect.signature(_fake).parameters) >= 3
        except (TypeError, ValueError):
            takes_language = False
        results = _fake(source, list(stdins), language) if takes_language else _fake(source, list(stdins))
    else:
        results = list(_fake)
    return [_clean(r) for r in results]


# ---------------------------------------------------------------- local runner (offline demo only, not a sandbox)
LOCAL_TIME_LIMIT_S = 5


LOCAL_COMPILE_LIMIT_S = 30


def _local_commands(language, folder):
    """(compile command or None, run command) for one language in `folder`. Pure, so tests can check it."""
    if language == "python":
        return None, [sys.executable, "-I", os.path.join(folder, "main.py")]
    if language == "cpp":
        exe = os.path.join(folder, "main.exe" if os.name == "nt" else "main")
        return [shutil.which("g++") or "g++", "-std=c++17", "-O2", "-o", exe, os.path.join(folder, "main.cpp")], [exe]
    if language == "java":
        return ([shutil.which("javac") or "javac", "-encoding", "UTF-8", os.path.join(folder, "Main.java")],
                [shutil.which("java") or "java", "-cp", folder, "Main"])
    if language == "javascript":
        return None, [shutil.which("node") or "node", os.path.join(folder, "index.js")]
    raise CodeRunnerError("runner_unavailable")


def _hide_folder(text, folder):
    """Removes the server's temp folder path from compiler and traceback text, so no server path reaches the browser."""
    if not text:
        return text
    for variant in {folder, folder.replace("\\", "/"), os.path.realpath(folder)}:
        text = text.replace(variant + os.sep, "").replace(variant + "/", "").replace(variant, ".")
    return text


def _run_local(source, stdins, language):
    if language not in available_languages():
        raise CodeRunnerError("runner_unavailable")
    results = []
    with tempfile.TemporaryDirectory(prefix="levelup-run-") as folder:
        main = os.path.join(folder, LANGUAGES[language]["file"])
        with open(main, "w", encoding="utf-8") as f:
            f.write(source)
        env = {"PYTHONIOENCODING": "utf-8", "PATH": os.environ.get("PATH", ""),
               "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),   # Windows needs SYSTEMROOT to start Python
               "TEMP": folder, "TMP": folder}                     # compilers need a temp folder
        build, command = _local_commands(language, folder)
        if build:
            try:
                built = subprocess.run(build, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                       cwd=folder, env=env, timeout=LOCAL_COMPILE_LIMIT_S)
            except subprocess.TimeoutExpired:
                raise CodeRunnerError("timeout") from None
            except OSError:
                raise CodeRunnerError("runner_unavailable") from None
            if built.returncode != 0:   # a compile error is the student's: shown like a crash on every test
                message = _text(_hide_folder(built.stderr or built.stdout or "Compilation failed.", folder))
                return [{"stdout": "", "stderr": message, "exception": "error"} for _ in stdins]
        for stdin in stdins:
            try:
                done = subprocess.run(command, input=stdin, capture_output=True, text=True,
                                      encoding="utf-8", errors="replace", cwd=folder, env=env,
                                      timeout=LOCAL_TIME_LIMIT_S)
                exception = None if done.returncode == 0 or done.stderr.strip() else "error"
                results.append({"stdout": _text(done.stdout), "stderr": _text(_hide_folder(done.stderr, folder)),
                                "exception": exception})
            except subprocess.TimeoutExpired:
                results.append({"stdout": "", "stderr": "", "exception": "time_limit"})
            except OSError:
                raise CodeRunnerError("runner_unavailable") from None
    return results


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
def _onecompiler_body(source, stdins, language):
    spec = LANGUAGES[language]
    return {"language": spec["onecompiler"], "stdin": list(stdins), "files": [{"name": spec["file"], "content": source}]}


def _post_once(source, stdins, key, language=DEFAULT_LANGUAGE):
    body = _onecompiler_body(source, stdins, language)
    headers = {"X-API-Key": key, "User-Agent": USER_AGENT, "Accept": "application/json",
               "Content-Type": "application/json"}
    return requests.post(ONECOMPILER_URL, json=body, headers=headers, timeout=REQUEST_TIMEOUT_S)


def _run_onecompiler(source, stdins, language):
    key = str(_setting("ONECOMPILER_API_KEY", "") or "").strip()
    if not key:
        raise CodeRunnerError("runner_unavailable")
    response = None
    for attempt in (1, 2):          # one retry, only for a connection error
        try:
            response = _post_once(source, stdins, key, language)
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
def run_batch(source, stdins, language=DEFAULT_LANGUAGE):
    """Run `source` (written in `language`, a key of LANGUAGES) once per entry of `stdins` in ONE provider call.
    Returns one result per stdin. The route validates the language first; an unknown one here is runner_unavailable."""
    if language not in LANGUAGES:
        raise CodeRunnerError("runner_unavailable")
    _check_caps(source, stdins)
    if not stdins:
        return []
    name = runner_name()
    if name == "fake":
        results = _run_fake(source, stdins, language)
    elif name == "local":
        results = _run_local(source, stdins, language)
    else:
        results = _run_onecompiler(source, stdins, language)
    if len(results) != len(stdins):
        raise CodeRunnerError("runner_unavailable")
    return results
