"""
Shared Gemini call wrapper with retry + fallback, used by both roadmap
generation and resume feedback. Extracted from roadmap_generator.py rather
than duplicated, since both need identical resilience against Gemini's
free-tier 503 UNAVAILABLE ("high demand") errors - a known, widely-reported,
ongoing issue across multiple Gemini model versions and tiers, confirmed
via search when first encountered during roadmap generation testing.

Both PRIMARY_MODEL and FALLBACK_MODEL were confirmed (via a live
client.models.get() call against the installed google-genai==2.23.0 SDK) to
have output_token_limit=65536 - the hard ceiling max_output_tokens below can
request.
"""

import os

from google import genai
from google.genai import types
from google.genai.errors import ServerError, ClientError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

PRIMARY_MODEL = "gemini-flash-latest"
# Alias rather than a pinned name, for the same reason as PRIMARY_MODEL: the
# previous pinned fallback (gemini-2.5-flash) was retired and started
# returning 404, which silently made this fallback useless.
FALLBACK_MODEL = "gemini-flash-lite-latest"


def _build_config(max_output_tokens, json_mode, system=None, timeout_s=None):
    """
    None (not an empty GenerateContentConfig) when no option is used, so
    passing config=None to generate_content is byte-for-byte the same call
    resume_feedback.py has always made - its default behavior (plain text
    back, no explicit output cap) is unchanged. system and timeout_s are
    new, optional and likewise absent from the config unless given.
    """
    if max_output_tokens is None and not json_mode and system is None and timeout_s is None:
        return None
    kwargs = {}
    if max_output_tokens is not None:
        kwargs["max_output_tokens"] = max_output_tokens
    if json_mode:
        kwargs["response_mime_type"] = "application/json"
    if system is not None:
        kwargs["system_instruction"] = system
    if timeout_s is not None:
        kwargs["http_options"] = types.HttpOptions(timeout=int(timeout_s * 1000))  # SDK takes milliseconds
    return types.GenerateContentConfig(**kwargs)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    retry=retry_if_exception_type(ServerError),
    reraise=True,
)
def _call_gemini(client, model, prompt, config):
    return client.models.generate_content(model=model, contents=prompt, config=config)


def _usage(response):
    meta = getattr(response, "usage_metadata", None)
    return (getattr(meta, "prompt_token_count", None), getattr(meta, "candidates_token_count", None))


def generate_with_retry(prompt, max_output_tokens=None, json_mode=False, system=None, timeout_s=None,
                        primary_model=None, fallback_model=None, return_meta=False):
    """
    Calls Gemini with the given prompt: up to 3 retries with exponential
    backoff on the primary model (only for ServerError - 503-class
    failures - never for ClientError, which won't succeed on retry against
    the same model), then one fallback attempt on a different model if the
    primary fails with a ServerError or a 429 quota error. Free-tier quota
    is per model, so a 429 on the primary says nothing about the fallback.
    Other ClientErrors (bad request, auth, ...) would fail identically on
    any model, so they don't trigger the fallback. Raises ValueError (not
    the raw Gemini exception) on total failure, for callers to handle
    uniformly.

    max_output_tokens (int) and json_mode (bool) are optional and both
    default to the prior behavior (no config object at all - see
    _build_config) - resume_feedback.py calls this with neither and gets
    plain text back, unchanged. A caller that wants Gemini to skip markdown
    code-fence wrapping and respond with raw JSON only should pass
    json_mode=True; _strip_code_fences() in roadmap_generator.py still
    handles the fenced case too, as a no-op safety net if a model ignores
    the mime type.

    Added for llm_client.py, all defaulting to the old behavior: system
    (system instruction), timeout_s (per-request HTTP timeout),
    primary_model / fallback_model (override the module's two model names),
    and return_meta=True, which returns {"text", "model_id", "input_tokens",
    "output_tokens"} instead of just the text.
    """
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    config = _build_config(max_output_tokens, json_mode, system, timeout_s)
    primary = primary_model or PRIMARY_MODEL
    fallback = fallback_model or FALLBACK_MODEL
    used_model = primary

    try:
        response = _call_gemini(client, primary, prompt, config)
    except (ServerError, ClientError) as primary_error:
        if isinstance(primary_error, ClientError) and primary_error.code != 429:
            raise ValueError(f"Gemini API call failed: {primary_error}")
        try:
            response = client.models.generate_content(model=fallback, contents=prompt, config=config)
            used_model = fallback
        except (ServerError, ClientError) as fallback_error:
            raise ValueError(
                "Gemini API call failed on both primary and fallback models. "
                f"Primary: {primary_error} | Fallback: {fallback_error}"
            )

    text = response.text.strip()
    if return_meta:
        in_tok, out_tok = _usage(response)
        return {"text": text, "model_id": used_model, "input_tokens": in_tok, "output_tokens": out_tok}
    return text
