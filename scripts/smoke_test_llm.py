"""
Smoke test for app/pipeline/llm_client.py with stubs only: a scripted fake
Bedrock client and a patched gemini_client.generate_with_retry. No network, no
database, no real credentials (the "secrets" used here are made-up strings).

Usage:
    PYTHONPATH=. python scripts/smoke_test_llm.py
"""
import io
import logging
import os
import sys
from unittest.mock import patch

from dotenv import load_dotenv
load_dotenv()

from app.config import Config
from app.pipeline import gemini_client, llm_client
from app.pipeline.llm_client import LLMError, generate

checks = []

FAKE_SECRET = "fake-secret-token-0123456789abcdef"
PROMPT_TEXT = "PROMPT-CANARY-do-not-log"
REPLY_TEXT = "REPLY-CANARY-do-not-log"
SCHEMA = {"type": "array", "items": {"type": "object", "required": ["title"], "properties": {"title": {"type": "string"}}}}


def check(description, condition):
    checks.append((description, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {description}")


class FakeClientError(Exception):
    """Same shape as botocore's ClientError: .response['Error']['Code']."""
    def __init__(self, code, status=400, message="boom"):
        super().__init__(message)
        self.response = {"Error": {"Code": code, "Message": message}, "ResponseMetadata": {"HTTPStatusCode": status}}


def ok_reply(text, in_tok=11, out_tok=7):
    return {"output": {"message": {"content": [{"text": text}]}}, "usage": {"inputTokens": in_tok, "outputTokens": out_tok}}


class FakeBedrock:
    """Plays back a script: each item is a reply dict or an exception to raise. Records every request."""
    def __init__(self, script):
        self.script, self.calls = list(script), []

    def converse(self, **request):
        self.calls.append(request)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class Env:
    """Temporarily set Config attributes / environment variables, restoring them afterwards."""
    def __init__(self, config=None, env=None):
        self.config, self.env, self.saved_cfg, self.saved_env = config or {}, env or {}, {}, {}

    def __enter__(self):
        for k, v in self.config.items():
            self.saved_cfg[k] = getattr(Config, k, None)
            setattr(Config, k, v)
        for k, v in self.env.items():
            self.saved_env[k] = os.environ.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return self

    def __exit__(self, *exc):
        for k, v in self.saved_cfg.items():
            setattr(Config, k, v)
        for k, v in self.saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


BEDROCK = {"LLM_PROVIDER": "bedrock", "AWS_REGION": "us-east-1", "ROADMAP_MODEL_ID": "model-primary",
           "FAST_MODEL_ID": "model-fast", "FALLBACK_MODEL_ID": "model-fallback", "ALT_PROVIDER_MODEL_ID": ""}


def with_fake_bedrock(script):
    fake = FakeBedrock(script)
    seen = {}
    llm_client._bedrock_clients.clear()   # the client is cached per (region, timeout)

    def factory(region, timeout_s):
        seen["region"], seen["timeout_s"] = region, timeout_s
        return fake
    return fake, seen, patch.object(llm_client, "_bedrock_client_factory", factory)


def forbidden_client(*args, **kwargs):
    raise AssertionError("smoke_test_llm must never construct a real Gemini client")


def main():
    # Safety net for the whole run: no real credentials are visible to the code under test,
    # and the Gemini SDK client cannot be built, so no test can reach the network by accident.
    # Tests that need a "configured" provider set made-up credentials in a nested Env.
    no_creds = {"GEMINI_API_KEY": None, "AWS_BEARER_TOKEN_BEDROCK": None, "AWS_ACCESS_KEY_ID": None,
                "AWS_SECRET_ACCESS_KEY": None}
    with Env(env=no_creds), patch.object(gemini_client.genai, "Client", forbidden_client),             patch.object(gemini_client, "generate_with_retry", forbidden_client):
        run()


def run():
    sleeps = []
    llm_client._sleep = sleeps.append   # backoff costs no real time

    # 1. primary success
    with Env({**BEDROCK, "LLM_TIMEOUT_S": 12.0}):
        fake, seen, p = with_fake_bedrock([ok_reply("hello", 12, 5)])
        with p:
            r = generate("roadmap", "p", system="be brief", max_output_tokens=99)
        check("primary success: text, provider, model, token counts returned",
              r["text"] == "hello" and r["provider"] == "bedrock" and r["model_id"] == "model-primary"
              and r["input_tokens"] == 12 and r["output_tokens"] == 5 and r["latency_s"] >= 0)
        check("primary success: one call, system prompt and token limit sent in Converse format",
              len(fake.calls) == 1 and fake.calls[0]["system"] == [{"text": "be brief"}]
              and fake.calls[0]["inferenceConfig"] == {"maxTokens": 99}
              and fake.calls[0]["modelId"] == "model-primary")
        check("task selects the model (fast -> FAST_MODEL_ID)", True)
        fake, _, p = with_fake_bedrock([ok_reply("x")])
        with p:
            r = generate("fast", "p")
        check("task 'fast' uses FAST_MODEL_ID", r["model_id"] == "model-fast")
        check("LLM_TIMEOUT_S (config) is passed to the bedrock client", seen["timeout_s"] == 12.0)

    # 2. throttling then success
    with Env(BEDROCK):
        sleeps.clear()
        fake, _, p = with_fake_bedrock([FakeClientError("ThrottlingException", 429), ok_reply("later")])
        with p:
            r = generate("roadmap", "p")
        check("throttling then success: retried once on the same model, backoff slept",
              r["text"] == "later" and len(fake.calls) == 2 and r["retries"] == 1 and sleeps == [2]
              and {c["modelId"] for c in fake.calls} == {"model-primary"})

    # 3. access denied is not retried
    with Env({**BEDROCK, "FALLBACK_MODEL_ID": ""}):
        sleeps.clear()
        fake, _, p = with_fake_bedrock([FakeClientError("AccessDeniedException", 403)])
        with p:
            try:
                generate("roadmap", "p")
                err = None
            except LLMError as exc:
                err = exc
        check("access denied: not retried (1 call, no sleep) and raises LLMError(kind=access)",
              err is not None and err.kind == "access" and len(fake.calls) == 1 and not sleeps)

    # 3b. validation error not retried and no fallback
    with Env(BEDROCK):
        fake, _, p = with_fake_bedrock([FakeClientError("ValidationException", 400)])
        with p:
            try:
                generate("roadmap", "p")
                err = None
            except LLMError as exc:
                err = exc
        check("validation error: not retried, fallback model not tried",
              err is not None and err.kind == "validation" and len(fake.calls) == 1)

    # 4. invalid JSON then corrected
    with Env(BEDROCK):
        fake, _, p = with_fake_bedrock([ok_reply("this is not json"), ok_reply('```json\n[{"title": "ok"}]\n```')])
        with p:
            r = generate("roadmap", "make steps", schema=SCHEMA)
        check("invalid JSON then corrected: parsed result returned after one correction retry",
              r["parsed"] == [{"title": "ok"}] and r["schema_retry"] is True and len(fake.calls) == 2)
        retry_prompt = fake.calls[1]["messages"][0]["content"][0]["text"]
        check("correction prompt quotes the problem and keeps the original prompt",
              "make steps" in retry_prompt and "not valid JSON" in retry_prompt)

    # 4b. valid JSON, wrong shape -> corrected
    with Env(BEDROCK):
        fake, _, p = with_fake_bedrock([ok_reply('[{"name": "x"}]'), ok_reply('[{"title": "fine"}]')])
        with p:
            r = generate("roadmap", "p", schema=SCHEMA)
        check("schema mismatch (missing required key) triggers the correction retry",
              r["parsed"] == [{"title": "fine"}] and "schema" in fake.calls[1]["messages"][0]["content"][0]["text"])

    # 5. invalid twice -> error
    with Env(BEDROCK):
        fake, _, p = with_fake_bedrock([ok_reply("nope"), ok_reply("still nope")])
        with p:
            try:
                generate("roadmap", "p", schema=SCHEMA)
                err = None
            except LLMError as exc:
                err = exc
        check("invalid twice: raises LLMError(kind=schema) after exactly 2 calls",
              err is not None and err.kind == "schema" and len(fake.calls) == 2)

    # 6. fallback model used
    with Env(BEDROCK):
        sleeps.clear()
        script = [FakeClientError("ThrottlingException", 429)] * 3 + [ok_reply("from fallback")]
        fake, _, p = with_fake_bedrock(script)
        with p:
            r = generate("roadmap", "p")
        check("fallback model used after the primary's 3 transient attempts",
              r["text"] == "from fallback" and r["model_id"] == "model-fallback"
              and [c["modelId"] for c in fake.calls] == ["model-primary"] * 3 + ["model-fallback"]
              and sleeps == [2, 4])
    with Env(BEDROCK):
        fake, _, p = with_fake_bedrock([FakeClientError("AccessDeniedException", 403), ok_reply("fb")])
        with p:
            r = generate("roadmap", "p")
        check("access denied on the primary model moves to the fallback model (still one try each)",
              r["model_id"] == "model-fallback" and len(fake.calls) == 2)

    # 6b. 5xx and timeouts are transient
    with Env(BEDROCK):
        fake, _, p = with_fake_bedrock([FakeClientError("InternalServerException", 500), TimeoutError("slow"), ok_reply("ok")])
        with p:
            r = generate("roadmap", "p")
        check("5xx and timeout errors are retried", r["text"] == "ok" and len(fake.calls) == 3)

    # 7. provider switch
    gemini_calls = []

    def fake_gemini(prompt, **kwargs):
        gemini_calls.append(kwargs)
        return {"text": '[{"title": "g"}]', "model_id": "gemini-x", "input_tokens": 3, "output_tokens": 2}

    with Env({**BEDROCK, "LLM_PROVIDER": "gemini", "ROADMAP_MODEL_ID": "", "LLM_TIMEOUT_S": 12.0}, {"GEMINI_API_KEY": FAKE_SECRET}):
        with patch.object(gemini_client, "generate_with_retry", fake_gemini):
            r = generate("roadmap", "p", schema=SCHEMA, max_output_tokens=50)
        check("gemini provider: delegates to gemini_client, returns tokens and model id",
              r["provider"] == "gemini" and r["model_id"] == "gemini-x" and r["input_tokens"] == 3
              and r["parsed"] == [{"title": "g"}])
        check("gemini provider: LLM_TIMEOUT_S and json mode passed through",
              gemini_calls[0]["timeout_s"] == 12.0 and gemini_calls[0]["json_mode"] is True
              and gemini_calls[0]["max_output_tokens"] == 50)

    with Env({**BEDROCK, "ALT_PROVIDER_MODEL_ID": ""}, {"GEMINI_API_KEY": FAKE_SECRET}):
        script = [FakeClientError("ThrottlingException", 429)] * 6
        fake, _, p = with_fake_bedrock(script)
        gemini_calls.clear()
        with p, patch.object(gemini_client, "generate_with_retry", fake_gemini):
            r = generate("roadmap", "p")
        check("provider switch: bedrock exhausted -> gemini takes over", r["provider"] == "gemini" and len(gemini_calls) == 1)

    with Env({**BEDROCK, "LLM_PROVIDER": "gemini", "ALT_PROVIDER_MODEL_ID": "bedrock-alt"},
             {"GEMINI_API_KEY": FAKE_SECRET, "AWS_BEARER_TOKEN_BEDROCK": FAKE_SECRET}):
        fake, _, p = with_fake_bedrock([ok_reply("alt reply")])

        def failing_gemini(prompt, **kwargs):
            raise ValueError("Gemini API call failed on both primary and fallback models.")
        with p, patch.object(gemini_client, "generate_with_retry", failing_gemini):
            r = generate("roadmap", "p")
        check("provider switch: gemini fails -> bedrock takes over using ALT_PROVIDER_MODEL_ID",
              r["provider"] == "bedrock" and r["model_id"] == "bedrock-alt")

    with Env({**BEDROCK, "LLM_PROVIDER": "gemini"}, {"GEMINI_API_KEY": FAKE_SECRET, "AWS_BEARER_TOKEN_BEDROCK": None,
                                                      "AWS_ACCESS_KEY_ID": None}):
        with patch.object(gemini_client, "generate_with_retry", failing_gemini):
            try:
                generate("roadmap", "p")
                err = None
            except LLMError as exc:
                err = exc
        check("no other provider configured: the original failure is raised as LLMError", err is not None and err.provider == "gemini")

    # 8. no secret / prompt text in any error or log
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.DEBUG)
    root = logging.getLogger()
    old_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    messages = []
    try:
        with Env(BEDROCK, {"AWS_BEARER_TOKEN_BEDROCK": FAKE_SECRET, "GEMINI_API_KEY": FAKE_SECRET}):
            leak = f"request failed using Bearer {FAKE_SECRET} for {PROMPT_TEXT}"
            fake, _, p = with_fake_bedrock([FakeClientError("ValidationException", 400, leak)])
            with p:
                try:
                    generate("roadmap", PROMPT_TEXT)
                except LLMError as exc:
                    messages.append(str(exc))
            fake, _, p = with_fake_bedrock([ok_reply(REPLY_TEXT)])
            with p:
                generate("roadmap", PROMPT_TEXT)

            def leaky_gemini(prompt, **kwargs):
                raise ValueError(f"Gemini API call failed: key={FAKE_SECRET} {PROMPT_TEXT}")
            with Env({"LLM_PROVIDER": "gemini"}), patch.object(gemini_client, "generate_with_retry", leaky_gemini):
                try:
                    generate("roadmap", PROMPT_TEXT)
                except LLMError as exc:
                    messages.append(str(exc))
            fake, _, p = with_fake_bedrock([ok_reply("bad"), ok_reply("worse " + REPLY_TEXT)])
            with p:
                try:
                    generate("roadmap", PROMPT_TEXT, schema=SCHEMA)
                except LLMError as exc:
                    messages.append(str(exc))
    finally:
        root.removeHandler(handler)
        root.setLevel(old_level)
    logged = stream.getvalue()
    check("no credential appears in any raised error", all(FAKE_SECRET not in m for m in messages) and len(messages) == 3)
    check("no credential appears in any log line", FAKE_SECRET not in logged and "Bearer" not in logged)
    check("neither prompt text nor reply text appears in logs or errors",
          PROMPT_TEXT not in logged and REPLY_TEXT not in logged
          and all(PROMPT_TEXT not in m and REPLY_TEXT not in m for m in messages))
    check("a successful call logs one line with task, model, tokens and latency",
          "llm_call task=roadmap provider=bedrock model=model-primary" in logged and "latency_s=" in logged)

    # 9. cost is unknown unless a price is configured
    with Env(BEDROCK):
        fake, _, p = with_fake_bedrock([ok_reply("a", 1000, 500)])
        with p:
            r = generate("roadmap", "p")
        check("cost is None by default (PRICE_PER_MTOK is empty)", Config.PRICE_PER_MTOK == {} and r["cost_usd"] is None)
    with Env({**BEDROCK, "PRICE_PER_MTOK": {"model-primary": {"input": 2.0, "output": 10.0}}}):
        fake, _, p = with_fake_bedrock([ok_reply("a", 1000, 500)])
        with p:
            r = generate("roadmap", "p")
        check("cost is computed only from configured prices", abs(r["cost_usd"] - 0.007) < 1e-12)

    # 10. misc
    with Env(BEDROCK):
        try:
            generate("slow", "p")
            err = None
        except LLMError as exc:
            err = exc
        check("unknown task raises LLMError(kind=config)", err is not None and err.kind == "config")
    with Env({**BEDROCK, "ROADMAP_MODEL_ID": "", "FALLBACK_MODEL_ID": ""}):
        try:
            generate("roadmap", "p")
            err = None
        except LLMError as exc:
            err = exc
        check("bedrock with no model ID configured fails clearly, without a call", err is not None and err.kind == "config")
    check("LLMError is a ValueError (existing handlers keep working)", issubclass(LLMError, ValueError))

    passed = sum(1 for _, ok in checks if ok)
    print(f"\n{passed}/{len(checks)} checks passed")
    sys.exit(0 if passed == len(checks) else 1)


if __name__ == "__main__":
    main()
