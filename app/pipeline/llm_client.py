"""
One entry point for every LLM call the app makes: generate(task, prompt, ...).

Providers: "gemini" (the default; delegates to gemini_client.generate_with_retry,
whose retry/fallback behavior is unchanged) or "bedrock" (boto3 bedrock-runtime
Converse API) or "openai_compat" (POST {LLM_BASE_URL}/chat/completions with `requests`; NVIDIA's
endpoint by default; the key variable is chosen from the base URL host, see _openai_key_variable; sent only as a bearer header). Which one is used comes from config.LLM_PROVIDER; which model
from the task: "roadmap" -> ROADMAP_MODEL_ID, "fast" -> FAST_MODEL_ID,
"fallback" -> FALLBACK_MODEL_ID. Credentials are never read here: boto3 and the
Gemini SDK take them from the environment themselves, and nothing in this
module logs or puts them in an error.

Failure handling, in order:
1. Transient errors (throttling, 5xx, timeouts) are retried with backoff on the
   same model. Access-denied, not-found and validation errors are never retried.
2. A model that is unusable (retries exhausted, or access denied / not found
   for that model) is followed by FALLBACK_MODEL_ID, if set and different.
   A validation error stops immediately: another model would reject it too.
3. If the whole provider fails and the OTHER provider is configured (Gemini:
   GEMINI_API_KEY set; Bedrock: AWS_REGION, ALT_PROVIDER_MODEL_ID and
   credentials in the environment), it is tried once.
4. Otherwise LLMError (a ValueError subclass, so existing handlers that catch
   ValueError keep working) with a message built from error codes only.

If a JSON schema is given, the reply is parsed (code fences stripped) and
validated with jsonschema; on failure the call is repeated ONCE with a
correction prompt that quotes the validation error; a second failure raises
LLMError(kind="schema").

Every call logs one line: task, provider, model, token counts, latency, cost
(or "unknown"), success. Never the prompt or the reply.
"""
import json
import logging
import os
import re
import threading
import time
from urllib.parse import urlparse

import jsonschema
import requests

from app.config import Config
from app.pipeline import gemini_client

logger = logging.getLogger(__name__)

TASKS = ("roadmap", "fast", "fallback")
_TASK_MODEL_ATTR = {"roadmap": "ROADMAP_MODEL_ID", "fast": "FAST_MODEL_ID", "fallback": "FALLBACK_MODEL_ID"}

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (2, 4)           # waits after attempt 1 and 2, same as gemini_client's
DEFAULT_TIMEOUT_S = 90

_TRANSIENT_CODES = {
    "ThrottlingException", "TooManyRequestsException", "ServiceUnavailableException",
    "InternalServerException", "ModelTimeoutException", "ModelNotReadyException",
    "RequestTimeout", "RequestTimeoutException",
}
_TRANSIENT_ERROR_NAMES = {
    "ReadTimeoutError", "ConnectTimeoutError", "ConnectionClosedError", "EndpointConnectionError",
    "ReadTimeout", "ConnectTimeout", "TimeoutError", "IncompleteReadError",
}
_MODEL_SCOPED_CODES = {"AccessDeniedException", "ResourceNotFoundException"}
_CREDENTIAL_CODES = {"UnrecognizedClientException", "ExpiredTokenException", "InvalidSignatureException",
                     "InvalidClientTokenId", "NoCredentialsError", "TokenRetrievalError"}

_sleep = time.sleep   # tests replace this so backoff costs no real time


class LLMError(ValueError):
    """The one error type generate() raises. Messages carry codes, never secrets or prompt text."""

    def __init__(self, message, kind="failed", task=None, provider=None):
        super().__init__(message)
        self.kind = kind          # transient | access | validation | too_large | schema | config | failed
        self.task = task
        self.provider = provider


# --------------------------------------------------------------------- helpers

def _setting(name, default=None):
    value = getattr(Config, name, default)
    return default if value is None else value


def _timeout_s():
    return float(_setting("LLM_TIMEOUT_S", DEFAULT_TIMEOUT_S))


def _openai_timeout_s():
    """openai_compat only: long generations (a roadmap phase took 178 s) need more than the 90 s default."""
    return float(_setting("LLM_TIMEOUT_S_OPENAI_COMPAT", 300.0))


def estimate_cost_usd(model_id, input_tokens, output_tokens):
    """USD for one call, or None when the model has no price in config.PRICE_PER_MTOK or counts are unknown."""
    price = (_setting("PRICE_PER_MTOK", {}) or {}).get(model_id)
    if not price or input_tokens is None or output_tokens is None:
        return None
    return (input_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000


def strip_code_fences(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _provider_configured(provider, model_id=None):
    if provider == "gemini":
        return bool(os.environ.get("GEMINI_API_KEY"))
    if provider == "openai_compat":
        return bool(_openai_api_key()) and bool(model_id)
    if provider == "bedrock":
        has_creds = bool(os.environ.get("AWS_BEARER_TOKEN_BEDROCK") or os.environ.get("AWS_ACCESS_KEY_ID"))
        return bool(_setting("AWS_REGION", "")) and has_creds and bool(model_id)
    return False


# --------------------------------------------------------------------- bedrock

def _make_bedrock_client(region, timeout_s):
    try:
        import boto3
        from botocore.config import Config as BotoConfig
    except ImportError:
        raise LLMError("The bedrock provider needs the boto3 package, which is not installed.", kind="config")
    return boto3.client(
        "bedrock-runtime", region_name=region,
        config=BotoConfig(read_timeout=timeout_s, connect_timeout=min(10, timeout_s), retries={"max_attempts": 1}),
    )


_bedrock_client_factory = _make_bedrock_client     # tests replace this with a fake
_bedrock_clients = {}


def _bedrock_client():
    region, timeout_s = _setting("AWS_REGION", ""), _timeout_s()
    key = (region, timeout_s)
    if key not in _bedrock_clients:
        _bedrock_clients[key] = _bedrock_client_factory(region, timeout_s)
    return _bedrock_clients[key]


def _error_code(exc):
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        return (response.get("Error") or {}).get("Code") or ""
    return ""


def _http_status(exc):
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        return (response.get("ResponseMetadata") or {}).get("HTTPStatusCode") or 0
    return 0


def _classify_bedrock_error(exc):
    """transient | model (try the fallback model) | credentials | validation"""
    code, name, status = _error_code(exc), type(exc).__name__, _http_status(exc)
    if code in _TRANSIENT_CODES or status >= 500 or name in _TRANSIENT_ERROR_NAMES or isinstance(exc, TimeoutError):
        return "transient", code or name
    if code in _MODEL_SCOPED_CODES:
        return "model", code
    if code in _CREDENTIAL_CODES or name in _CREDENTIAL_CODES:
        return "credentials", code or name
    return "validation", code or name


def _bedrock_once(model_id, prompt, system, max_output_tokens):
    request = {
        "modelId": model_id,
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
    }
    if system:
        request["system"] = [{"text": system}]
    if max_output_tokens:
        request["inferenceConfig"] = {"maxTokens": max_output_tokens}
    response = _bedrock_client().converse(**request)
    blocks = response["output"]["message"]["content"]
    text = "".join(b.get("text", "") for b in blocks).strip()
    usage = response.get("usage") or {}
    return {"text": text, "model_id": model_id,
            "input_tokens": usage.get("inputTokens"), "output_tokens": usage.get("outputTokens")}


def _call_bedrock(task, models, prompt, system, max_output_tokens):
    """Try each model in order; returns (raw_result, retries). Raises LLMError."""
    if not models:
        raise LLMError("No model ID is configured for the bedrock provider.", kind="config", task=task, provider="bedrock")
    last_kind, last_code, retries = "failed", "", 0
    for model_id in models:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                return _bedrock_once(model_id, prompt, system, max_output_tokens), retries
            except LLMError:
                raise
            except Exception as exc:  # boto3 raises many types; classify by code, not by class
                kind, code = _classify_bedrock_error(exc)
                last_kind, last_code = kind, code
                if kind == "transient" and attempt < MAX_ATTEMPTS:
                    retries += 1
                    _sleep(BACKOFF_SECONDS[attempt - 1])
                    continue
                break
        if last_kind == "validation":
            raise LLMError(f"bedrock rejected the request ({last_code}).", kind="validation", task=task, provider="bedrock")
        if last_kind == "credentials":
            break   # every model would fail the same way; let the caller try the other provider
    kind = {"transient": "transient", "model": "access", "credentials": "access"}.get(last_kind, "failed")
    raise LLMError(f"bedrock call failed ({last_kind}: {last_code}).", kind=kind, task=task, provider="bedrock")


# ---------------------------------------------------------- openai-compatible (HTTP)

class _RateLimiter:
    """
    Spaces request START times at least 60/rpm seconds apart, across all threads: each caller
    reserves the next free slot under a lock and then sleeps outside it until the slot arrives, so
    parallel phase writers and retries can never exceed the rate, and nobody is refused - they wait.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._next_slot = 0.0

    def acquire(self, rpm):
        interval = 60.0 / max(1, rpm)
        with self._lock:
            now = _monotonic()
            slot = max(now, self._next_slot)
            self._next_slot = slot + interval
        wait = slot - now
        if wait > 0:
            _limiter_sleep(wait)
        return wait


_monotonic = time.monotonic        # tests replace these two to observe spacing without real waiting
_limiter_sleep = time.sleep
_limiter = _RateLimiter()
_OC_MAX_RETRY_AFTER_S = 120
_CHARS_PER_TOKEN = 3.5             # rough prompt-size estimate: characters / 3.5


def _openai_key_variable(base_url=None):
    """Name of the Config/env variable that holds the key for this endpoint, chosen by host."""
    host = (urlparse(base_url if base_url is not None else _setting("LLM_BASE_URL", "")).hostname or "").lower()
    for suffix, variable in (("groq.com", "GROQ_API_KEY"), ("nvidia.com", "NVIDIA_API_KEY")):
        if host == suffix or host.endswith("." + suffix):
            return variable
    return "LLM_API_KEY"


def _openai_api_key():
    return _setting(_openai_key_variable(), "") or ""


_DURATION_PART = re.compile(r"(\d+(?:\.\d+)?)(ms|h|m|s)")
_DURATION_SECONDS = {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001}


def parse_duration_s(value):
    """'27.705s' -> 27.705, '1m26.4s' -> 86.4, '500ms' -> 0.5, a bare number -> seconds; None if unreadable."""
    if value is None:
        return None
    text = str(value).strip().lower().replace(" ", "")
    try:
        return max(0.0, float(text))
    except ValueError:
        pass
    parts = _DURATION_PART.findall(text)
    if not parts or "".join(n + u for n, u in parts) != text:
        return None
    return sum(float(n) * _DURATION_SECONDS[u] for n, u in parts)


def _int_or_none(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def parse_rate_headers(headers):
    """{'remaining_tokens', 'limit_tokens', 'reset_s', 'retry_after_s'}; any of them None when absent or unreadable."""
    lowered = {str(k).lower(): v for k, v in dict(headers or {}).items()}
    return {"remaining_tokens": _int_or_none(lowered.get("x-ratelimit-remaining-tokens")),
            "limit_tokens": _int_or_none(lowered.get("x-ratelimit-limit-tokens")),
            "reset_s": parse_duration_s(lowered.get("x-ratelimit-reset-tokens")),
            "retry_after_s": parse_duration_s(lowered.get("retry-after"))}


def estimate_tokens(prompt, system=None):
    return int((len(prompt or "") + len(system or "")) / _CHARS_PER_TOKEN) + 1


class _TokenPacer:
    """
    Token-aware pacing shared by every thread. Knows the remaining tokens-per-minute from the provider's
    x-ratelimit-* headers (when it sends them) and, if LLM_MAX_TPM is set, from a client-side 60 s window of
    estimated/actual tokens. reserve() returns how long the caller must wait before sending; the wait is
    served by the caller outside the lock. Only what the provider counts is counted: input + output tokens,
    never max_tokens.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.reset()

    def reset(self):
        self.remaining = None      # tokens left in the current window, from the last response headers
        self.limit = None
        self._reset_at = None      # monotonic time at which the window refills
        self._in_flight = 0        # estimated tokens of requests sent but not yet answered
        self._window = []          # [start_time, tokens] per request, for LLM_MAX_TPM

    def assume_refreshed(self):
        with self._lock:
            self.remaining, self._reset_at = None, None

    def reserve(self, estimate, max_tpm=0):
        """(seconds to wait before sending, entry to pass to release())."""
        with self._lock:
            now = _monotonic()
            wait = 0.0
            if self.remaining is not None and self._reset_at is not None:
                if self._reset_at <= now:
                    self.remaining, self._reset_at = None, None
                elif estimate > self.remaining - self._in_flight:
                    wait = self._reset_at - now
                    self.remaining, self._reset_at = None, None     # after the wait the window has refilled
            if max_tpm and max_tpm > 0:
                self._window = [e for e in self._window if e[0] > now - 60.0]
                running = sum(e[1] for e in self._window)
                if self._window and running + estimate > max_tpm:
                    free_at = now
                    for start, tokens in sorted(self._window):
                        if running + estimate <= max_tpm:
                            break
                        running -= tokens
                        free_at = start + 60.0
                    wait = max(wait, free_at - now)
            wait = min(max(wait, 0.0), float(_OC_MAX_RETRY_AFTER_S))
            entry = [now + wait, estimate]
            self._window.append(entry)
            self._in_flight += estimate
            return wait, entry

    def update(self, rate):
        """Take the numbers from one response's headers (any may be missing)."""
        with self._lock:
            if rate.get("limit_tokens") is not None:
                self.limit = rate["limit_tokens"]
            if rate.get("remaining_tokens") is not None:
                self.remaining = rate["remaining_tokens"]
                if rate.get("reset_s") is not None:
                    self._reset_at = _monotonic() + rate["reset_s"]

    def release(self, entry, actual_tokens=None):
        with self._lock:
            self._in_flight = max(0, self._in_flight - entry[1])
            if actual_tokens is not None:
                entry[1] = actual_tokens


_pacer = _TokenPacer()


class _HttpFailure(Exception):
    def __init__(self, kind, code, retry_after):
        super().__init__(f"{kind}:{code}")
        self.kind, self.code, self.retry_after = kind, code, retry_after   # kind: transient|credentials|model|too_large|validation


def _openai_once(model_id, prompt, system, max_output_tokens):
    """One HTTP request. Returns the raw result dict, or raises _HttpFailure(kind, code, retry_after)."""
    url = f"{_setting('LLM_BASE_URL', '')}/chat/completions"
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    body = {"model": model_id, "messages": messages}
    if max_output_tokens:
        body["max_tokens"] = max_output_tokens
    effort = _setting("LLM_REASONING_EFFORT", "")
    if effort:
        body["reasoning_effort"] = effort
    headers = {"Authorization": f"Bearer {_openai_api_key()}", "Content-Type": "application/json"}
    estimate = estimate_tokens(prompt, system)
    token_wait, entry = _pacer.reserve(estimate, int(_setting("LLM_MAX_TPM", 0) or 0))
    actual = None
    try:
        if token_wait > 0:
            logger.info("llm_token_wait seconds=%.1f estimated_tokens=%s", token_wait, estimate)
            _limiter_sleep(token_wait)
        _limiter.acquire(int(_setting("LLM_MAX_RPM", 30)))
        try:
            response = requests.post(url, headers=headers, json=body, timeout=_openai_timeout_s())
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            raise _HttpFailure("transient", type(exc).__name__, None)
        except requests.exceptions.RequestException as exc:
            raise _HttpFailure("validation", type(exc).__name__, None)
        rate = parse_rate_headers(getattr(response, "headers", None))
        _pacer.update(rate)
        status = response.status_code
        reset_wait = None if rate["reset_s"] is None else min(_OC_MAX_RETRY_AFTER_S, rate["reset_s"])
        if status == 413:
            limit = rate["limit_tokens"] or int(_setting("LLM_MAX_TPM", 0) or 0) or "unknown"
            logger.warning("llm_request_too_large estimated_tokens=%s limit_tokens=%s", estimate, limit)
            raise _HttpFailure("too_large", "413", None)
        if status == 429 or status >= 500:
            retry_after = rate["retry_after_s"]
            if retry_after is None:
                retry_after = reset_wait if status == 429 else None
            elif retry_after is not None:
                retry_after = min(_OC_MAX_RETRY_AFTER_S, retry_after)
            raise _HttpFailure("transient", str(status), retry_after)
        if status in (401, 403):
            raise _HttpFailure("credentials", str(status), None)
        if status == 404:
            raise _HttpFailure("model", str(status), None)
        if status >= 400:
            raise _HttpFailure("validation", str(status), None)
        try:
            data = response.json()
            text = (data["choices"][0]["message"]["content"] or "").strip()
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise _HttpFailure("validation", "malformed_response", None)
        usage = data.get("usage") if isinstance(data, dict) else None
        usage = usage if isinstance(usage, dict) else {}
        if usage.get("prompt_tokens") is not None and usage.get("completion_tokens") is not None:
            actual = usage["prompt_tokens"] + usage["completion_tokens"]
        return {"text": text, "model_id": model_id,
                "input_tokens": usage.get("prompt_tokens"), "output_tokens": usage.get("completion_tokens")}
    finally:
        _pacer.release(entry, actual)


def _call_openai_compat(task, models, prompt, system, max_output_tokens):
    """Try each model in order; returns (raw_result, retries). Same retry rules as bedrock; raises LLMError."""
    if not models:
        raise LLMError("No model ID is configured for the openai_compat provider.", kind="config", task=task, provider="openai_compat")
    if not _openai_api_key():
        raise LLMError(f"{_openai_key_variable()} is not set.", kind="config", task=task, provider="openai_compat")
    last_kind, last_code, retries = "failed", "", 0
    for model_id in models:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                return _openai_once(model_id, prompt, system, max_output_tokens), retries
            except _HttpFailure as failure:
                last_kind, last_code = failure.kind, failure.code
                if failure.kind == "transient" and attempt < MAX_ATTEMPTS:
                    retries += 1
                    wait = failure.retry_after if failure.retry_after is not None else BACKOFF_SECONDS[attempt - 1]
                    _sleep(wait)
                    _pacer.assume_refreshed()    # the wait above covered the token reset
                    continue
                break
        if last_kind == "too_large":
            raise LLMError("openai_compat: request too large for the tokens-per-minute limit (413); not retried.",
                           kind="too_large", task=task, provider="openai_compat")
        if last_kind == "validation":
            raise LLMError(f"openai_compat rejected the request ({last_code}).", kind="validation", task=task, provider="openai_compat")
        if last_kind == "credentials":
            break
    kind = {"transient": "transient", "model": "access", "credentials": "access"}.get(last_kind, "failed")
    raise LLMError(f"openai_compat call failed ({last_kind}: {last_code}).", kind=kind, task=task, provider="openai_compat")


# --------------------------------------------------------------------- gemini

_GEMINI_STATUS_WORDS = ("RESOURCE_EXHAUSTED", "UNAVAILABLE", "PERMISSION_DENIED", "INVALID_ARGUMENT",
                        "DEADLINE_EXCEEDED", "INTERNAL", "NOT_FOUND", "UNAUTHENTICATED")


def _gemini_failure_summary(exc):
    """HTTP codes and status words found in gemini_client's error text; never the free text itself."""
    text = str(exc)
    found = re.findall(r"[45]\d\d", text) + [w for w in _GEMINI_STATUS_WORDS if w in text]
    return ", ".join(dict.fromkeys(found)) or "no status reported"


def _call_gemini(task, primary, fallback, prompt, system, max_output_tokens, json_mode):
    kwargs = {"max_output_tokens": max_output_tokens, "json_mode": json_mode}
    if system is not None:
        kwargs["system"] = system
    if primary:
        kwargs["primary_model"] = primary
    if fallback:
        kwargs["fallback_model"] = fallback
    kwargs["timeout_s"] = _timeout_s()
    kwargs["return_meta"] = True
    try:
        result = gemini_client.generate_with_retry(prompt, **kwargs)
    except LLMError:
        raise
    except ValueError as exc:     # gemini_client's uniform "total failure" error
        raise LLMError(f"gemini call failed ({_gemini_failure_summary(exc)}).", kind="failed", task=task, provider="gemini")
    except Exception as exc:
        raise LLMError(f"gemini call failed ({type(exc).__name__}).", kind="failed", task=task, provider="gemini")
    if isinstance(result, str):   # a stub (or an older gemini_client) that returns bare text
        result = {"text": result, "model_id": primary or gemini_client.PRIMARY_MODEL,
                  "input_tokens": None, "output_tokens": None}
    return result, 0


# ------------------------------------------------------------------- dispatch

def _models_for(provider, task):
    """(primary_model_id or None, fallback_model_id or None) for the PRIMARY provider."""
    primary = _setting(_TASK_MODEL_ATTR[task], "") or None
    fallback = _setting("FALLBACK_MODEL_ID", "") or None
    if fallback == primary:
        fallback = None
    return primary, fallback


def _call_provider(provider, task, is_primary, prompt, system, max_output_tokens, json_mode):
    if is_primary:
        primary, fallback = _models_for(provider, task)
    else:
        primary, fallback = (_setting("ALT_PROVIDER_MODEL_ID", "") or None), None
    if provider == "gemini":
        return _call_gemini(task, primary, fallback, prompt, system, max_output_tokens, json_mode)
    if provider == "bedrock":
        return _call_bedrock(task, [m for m in (primary, fallback) if m], prompt, system, max_output_tokens)
    if provider == "openai_compat":
        return _call_openai_compat(task, [m for m in (primary, fallback) if m], prompt, system, max_output_tokens)
    raise LLMError(f"Unknown LLM provider {provider!r} (expected 'gemini', 'bedrock' or 'openai_compat').", kind="config", task=task)


def _dispatch(task, prompt, system, max_output_tokens, json_mode):
    """One logical call: primary provider, then (if configured) the other. Returns (raw, provider, retries)."""
    provider = _setting("LLM_PROVIDER", "gemini")
    other = "bedrock" if provider == "gemini" else "gemini"
    try:
        raw, retries = _call_provider(provider, task, True, prompt, system, max_output_tokens, json_mode)
        return raw, provider, retries
    except LLMError as first_error:
        if first_error.kind in ("validation", "config", "too_large"):
            raise
        alt_model = _setting("ALT_PROVIDER_MODEL_ID", "") or None
        if not _provider_configured(other, alt_model):
            raise
        logger.warning("llm_failover task=%s from=%s to=%s kind=%s", task, provider, other, first_error.kind)
        try:
            raw, retries = _call_provider(other, task, False, prompt, system, max_output_tokens, json_mode)
        except LLMError as second_error:
            raise LLMError(f"{provider} failed ({first_error.kind}); {other} failed ({second_error.kind}).",
                           kind=first_error.kind, task=task, provider=provider)
        return raw, other, retries


def _parse_and_validate(text, schema):
    """(parsed, error_message). error_message None means success."""
    try:
        parsed = json.loads(strip_code_fences(text))
    except (json.JSONDecodeError, ValueError) as exc:
        return None, f"not valid JSON ({exc})"
    if schema is not None:
        try:
            jsonschema.validate(parsed, schema)
        except jsonschema.ValidationError as exc:
            # Deliberately not exc.message: it quotes the offending value, i.e. reply text.
            path = "/".join(str(p) for p in exc.absolute_path) or "(root)"
            detail = f"rule '{exc.validator}'"
            if exc.validator == "required":
                missing = re.match(r"^'([^']{1,60})' is a required property", exc.message)
                if missing:
                    detail += f", missing key '{missing.group(1)}'"
            return None, f"does not match the schema at {path} ({detail})"
    return parsed, None


def generate(task, prompt, system=None, schema=None, max_output_tokens=None, json_mode=False):
    """
    Returns {text, parsed, model_id, provider, input_tokens, output_tokens, latency_s,
    cost_usd, retries, schema_retry}. text is code-fence-stripped when JSON was requested
    (json_mode or schema); parsed is the decoded JSON, or None when no JSON was requested
    (or json_mode alone was requested and the reply wasn't JSON). Raises LLMError.
    """
    if task not in TASKS:
        raise LLMError(f"Unknown LLM task {task!r} (expected one of {TASKS}).", kind="config")
    wants_json = json_mode or schema is not None
    started = time.monotonic()
    provider, raw, retries, schema_retry = None, None, 0, False
    try:
        raw, provider, retries = _dispatch(task, prompt, system, max_output_tokens, wants_json)
        text, parsed = raw["text"], None
        if wants_json:
            text = strip_code_fences(text)
            parsed, problem = _parse_and_validate(text, schema)
            if problem and schema is not None:
                schema_retry = True
                correction = (
                    f"{prompt}\n\nYour previous reply was {problem}. Reply again with ONLY valid JSON"
                    " that matches the required structure - no markdown, no explanation."
                )
                raw, provider, more = _dispatch(task, correction, system, max_output_tokens, True)
                retries += more
                text = strip_code_fences(raw["text"])
                parsed, problem = _parse_and_validate(text, schema)
                if problem:
                    raise LLMError(f"The model's reply {problem} (after one correction retry).",
                                   kind="schema", task=task, provider=provider)
    except LLMError as exc:
        latency = time.monotonic() - started
        logger.warning("llm_call task=%s provider=%s ok=False kind=%s latency_s=%.2f",
                       task, exc.provider or provider, exc.kind, latency)
        exc.task = exc.task or task
        raise

    latency = time.monotonic() - started
    model_id = raw.get("model_id")
    cost = estimate_cost_usd(model_id, raw.get("input_tokens"), raw.get("output_tokens"))
    logger.info("llm_call task=%s provider=%s model=%s in_tokens=%s out_tokens=%s latency_s=%.2f cost_usd=%s ok=True",
                task, provider, model_id, raw.get("input_tokens"), raw.get("output_tokens"), latency,
                "unknown" if cost is None else f"{cost:.6f}")
    return {
        "text": text, "parsed": parsed, "model_id": model_id, "provider": provider,
        "input_tokens": raw.get("input_tokens"), "output_tokens": raw.get("output_tokens"),
        "latency_s": latency, "cost_usd": cost, "retries": retries, "schema_retry": schema_retry,
    }
