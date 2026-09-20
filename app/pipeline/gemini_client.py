"""
Shared Gemini call wrapper with retry + fallback, used by both roadmap
generation and resume feedback. Extracted from roadmap_generator.py rather
than duplicated, since both need identical resilience against Gemini's
free-tier 503 UNAVAILABLE ("high demand") errors - a known, widely-reported,
ongoing issue across multiple Gemini model versions and tiers, confirmed
via search when first encountered during roadmap generation testing.
"""

import os

from google import genai
from google.genai.errors import ServerError, ClientError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

PRIMARY_MODEL = "gemini-flash-latest"
# Alias rather than a pinned name, for the same reason as PRIMARY_MODEL: the
# previous pinned fallback (gemini-2.5-flash) was retired and started
# returning 404, which silently made this fallback useless.
FALLBACK_MODEL = "gemini-flash-lite-latest"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    retry=retry_if_exception_type(ServerError),
    reraise=True,
)
def _call_gemini(client, model, prompt):
    return client.models.generate_content(model=model, contents=prompt)


def generate_with_retry(prompt):
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
    """
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    try:
        response = _call_gemini(client, PRIMARY_MODEL, prompt)
    except (ServerError, ClientError) as primary_error:
        if isinstance(primary_error, ClientError) and primary_error.code != 429:
            raise ValueError(f"Gemini API call failed: {primary_error}")
        try:
            response = client.models.generate_content(model=FALLBACK_MODEL, contents=prompt)
        except (ServerError, ClientError) as fallback_error:
            raise ValueError(
                "Gemini API call failed on both primary and fallback models. "
                f"Primary: {primary_error} | Fallback: {fallback_error}"
            )

    return response.text.strip()
