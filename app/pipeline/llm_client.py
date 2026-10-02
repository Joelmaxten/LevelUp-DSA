"""
One entry point for every LLM call the app makes: generate(task, prompt, ...).

Providers: "gemini" (the default; delegates to gemini_client.generate_with_retry,
whose retry/fallback behavior is unchanged) or "bedrock" (boto3 bedrock-runtime
Converse API). Which one is used comes from config.LLM_PROVIDER; which model
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
import time

import jsonschema

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
        self.kind = kind          # transient | access | validation | schema | config | failed
        self.task = task
        self.provider = provider


# --------------------------------------------------------------------- helpers

def _setting(name, default=None):
    value = getattr(Config, name, default)
    return default if value is None else value


def _timeout_s():
    return float(_setting("LLM_TIMEOUT_S", DEFAULT_TIMEOUT_S))


_SECRET_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)", re.I)
_SECRET_SHAPES = re.compile(r"(Bearer\s+\S+|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_\-]{20,}|[A-Za-z0-9+/=_\-]{40,})")


def _redact(text):
    """Remove anything that looks like (or is exactly) a credential from a message."""
    text = str(text)
    for name, value in os.environ.items():
        if value and len(value) >= 6 and _SECRET_NAME.search(name):
            text = text.replace(value, "[redacted]")
    return _SECRET_SHAPES.sub("[redacted]", text)[:300]


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
    key = (region, timeout_s, id(_bedrock_client_factory))
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


# --------------------------------------------------------------------- gemini

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
        raise LLMError(f"gemini call failed: {_redact(exc)}", kind="failed", task=task, provider="gemini")
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
    raise LLMError(f"Unknown LLM provider {provider!r} (expected 'gemini' or 'bedrock').", kind="config", task=task)


def _dispatch(task, prompt, system, max_output_tokens, json_mode):
    """One logical call: primary provider, then (if configured) the other. Returns (raw, provider, retries)."""
    provider = _setting("LLM_PROVIDER", "gemini")
    other = "bedrock" if provider == "gemini" else "gemini"
    try:
        raw, retries = _call_provider(provider, task, True, prompt, system, max_output_tokens, json_mode)
        return raw, provider, retries
    except LLMError as first_error:
        if first_error.kind in ("validation", "config"):
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
            path = "/".join(str(p) for p in exc.absolute_path) or "(root)"
            return None, f"does not match the schema at {path}: {exc.message[:200]}"
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
