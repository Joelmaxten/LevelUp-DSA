"""
Generates a personalized roadmap for a student using RAG: retrieves relevant
knowledge base chunks for their top-ranked career path via FAISS, augments a
prompt with those chunks + their conversation signals, and calls Gemini to
generate a structured, personalized set of roadmap steps.

Per the master doc's anti-hallucination design, the prompt explicitly
constrains the LLM to only draw on retrieved content - it has no autonomy
to invent career advice outside what FAISS actually returned.

NOTE: This module depends on a built FAISS index (app/pipeline/rag.py's
load_index()) which is machine-local, gitignored generated data - not every
dev machine will have it. See PROJECT_BIOGRAPHY.md for which machine actually
has the index built.

Gemini's free tier returns intermittent 503 UNAVAILABLE ("high demand")
errors - a widely-reported, ongoing issue across multiple Gemini model
versions, not specific to this project. To keep demos reliable, calls retry
with backoff on the primary model, then fall back once to an older model
before giving up entirely.
"""

import json
import os

from google import genai
from google.genai.errors import ServerError, ClientError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.pipeline.rag import search

PRIMARY_MODEL = "gemini-flash-latest"
FALLBACK_MODEL = "gemini-2.5-flash"


def _build_prompt(career_path, retrieved_chunks, conversation_signals):
    context_text = "\n\n".join(
        f"[Source: {c['source']}]\n{c['text']}" for c in retrieved_chunks
    )

    return f"""You are generating a personalized learning roadmap for a student
pursuing the career path: {career_path}

Student context:
- Main goal: {conversation_signals.get('goal', 'not specified')}
- Wants to avoid: {conversation_signals.get('avoid', 'not specified')}
- Target company type: {conversation_signals.get('target_company', 'not specified')}

You must base the roadmap ONLY on the reference material below. Do not
invent skills, tools, or steps that are not grounded in this material.

Reference material:
{context_text}

Generate 8-12 roadmap steps. Respond ONLY with valid JSON, no markdown
formatting, no backticks, no preamble - an array of objects, each with
exactly these keys: "step_number" (int), "title" (string, short),
"description" (string, 1-2 sentences explaining why this step matters
for this student specifically, referencing their goal/context where relevant)."""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    retry=retry_if_exception_type(ServerError),
    reraise=True,
)
def _call_gemini(client, model, prompt):
    return client.models.generate_content(model=model, contents=prompt)


def generate_roadmap(career_path, conversation_signals, index, chunks, top_k=8):
    """
    career_path: the student's #1 ranked career path (string).
    conversation_signals: CareerProfile.conversation_signals dict.
    index, chunks: the loaded FAISS index + metadata (from rag.load_index()).

    Returns (steps, retrieved_chunks_audit) - steps is the parsed list of
    dicts, retrieved_chunks_audit is a lightweight record (source + score
    only, not full text) of what grounded this generation.
    """
    retrieved = search(career_path, index, chunks, top_k=top_k, career_path=career_path)

    if not retrieved:
        raise ValueError(
            f"No knowledge base content found for career path: {career_path!r}. "
            "Cannot generate a grounded roadmap without retrieved context."
        )

    prompt = _build_prompt(career_path, retrieved, conversation_signals)
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    try:
        response = _call_gemini(client, PRIMARY_MODEL, prompt)
    except ServerError:
        # Primary model exhausted its retries - try the fallback model once,
        # unguarded (if this also fails, let it raise up as-is).
        try:
            response = client.models.generate_content(model=FALLBACK_MODEL, contents=prompt)
        except (ServerError, ClientError) as e:
            raise ValueError(f"Gemini API call failed on both primary and fallback models: {e}")
    except ClientError as e:
        # Client errors (bad request, auth, etc.) are never worth retrying.
        raise ValueError(f"Gemini API call failed: {e}")

    raw_text = response.text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    try:
        steps = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned invalid JSON: {e}\nRaw response: {raw_text[:500]}")

    retrieved_chunks_audit = [
        {"source": c["source"], "score": c["score"]} for c in retrieved
    ]

    return steps, retrieved_chunks_audit
