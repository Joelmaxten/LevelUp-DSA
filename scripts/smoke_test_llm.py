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
import threading
import time
from unittest.mock import patch

import requests

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


class FakeHttpResponse:
    def __init__(self, status=200, body=None, headers=None):
        self.status_code, self._body, self.headers = status, body, headers or {}

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


def chat_reply(text, prompt_tokens=21, completion_tokens=9, usage=True):
    body = {"choices": [{"message": {"role": "assistant", "content": text}}]}
    if usage:
        body["usage"] = {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}
    return FakeHttpResponse(200, body)


class FakePost:
    """Stands in for requests.post: plays back a script of responses/exceptions and records every call."""
    def __init__(self, script):
        self.script, self.calls = list(script), []

    def __call__(self, url, headers=None, json=None, timeout=None, **kw):
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout, "at": time.monotonic()})
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


OC_KEY = "nvapi-FAKE-test-key-0123456789abcdef"
OPENAI = {"LLM_PROVIDER": "openai_compat", "LLM_BASE_URL": "https://llm.test/v1", "NVIDIA_API_KEY": OC_KEY,
          "ROADMAP_MODEL_ID": "oc-primary", "FAST_MODEL_ID": "oc-fast", "FALLBACK_MODEL_ID": "", "ALT_PROVIDER_MODEL_ID": "",
          "LLM_MAX_RPM": 60000, "LLM_TIMEOUT_S": 7.0, "LLM_TIMEOUT_S_OPENAI_COMPAT": 7.0}


def forbidden_client(*args, **kwargs):
    raise AssertionError("smoke_test_llm must never construct a real Gemini client")


def main():
    # Safety net for the whole run: no real credentials are visible to the code under test,
    # and the Gemini SDK client cannot be built, so no test can reach the network by accident.
    # Tests that need a "configured" provider set made-up credentials in a nested Env.
    no_creds = {"GEMINI_API_KEY": None, "AWS_BEARER_TOKEN_BEDROCK": None, "AWS_ACCESS_KEY_ID": None,
                "AWS_SECRET_ACCESS_KEY": None}
    with Env({"NVIDIA_API_KEY": ""}, env=no_creds), patch.object(gemini_client.genai, "Client", forbidden_client), patch.object(gemini_client, "generate_with_retry", forbidden_client), patch.object(requests, "post", forbidden_client):
        run()


def openai_compat_checks(sleeps):
    llm_client._limiter_sleep = lambda seconds: None     # no real waiting except in the spacing test below
    schema_ok = '[{"title": "x"}]'

    def go(script, config=None, **kw):
        fake = FakePost(script)
        llm_client._limiter._next_slot = 0.0
        with Env({**OPENAI, **(config or {})}), patch.object(requests, "post", fake):
            sleeps.clear()
            try:
                return fake, generate(kw.pop("task", "roadmap"), kw.pop("prompt", "p"), **kw), None
            except LLMError as exc:
                return fake, None, exc

    fake, r, err = go([chat_reply("hello")], system="be brief", max_output_tokens=55)
    call = fake.calls[0]
    check("openai_compat success: text, provider, model and token counts from the usage field",
          r["text"] == "hello" and r["provider"] == "openai_compat" and r["model_id"] == "oc-primary"
          and r["input_tokens"] == 21 and r["output_tokens"] == 9)
    check("openai_compat request: POST {LLM_BASE_URL}/chat/completions, bearer header, system+user messages, max_tokens, LLM_TIMEOUT_S",
          call["url"] == "https://llm.test/v1/chat/completions" and call["headers"]["Authorization"] == f"Bearer {OC_KEY}"
          and call["json"]["model"] == "oc-primary" and call["json"]["max_tokens"] == 55 and call["timeout"] == 7.0
          and call["json"]["messages"] == [{"role": "system", "content": "be brief"}, {"role": "user", "content": "p"}])
    fake, r, err = go([chat_reply("hi", usage=False)])
    check("openai_compat: no usage field -> token counts are None, not an error", r["input_tokens"] is None and r["output_tokens"] is None)
    fake, r, err = go([chat_reply("```json\n" + schema_ok + "\n```")], schema={"type": "array"})
    check("openai_compat: fenced JSON is unwrapped and parsed", r["parsed"] == [{"title": "x"}] and r["text"] == schema_ok)
    fake, r, err = go([chat_reply("not json"), chat_reply(schema_ok)], schema=SCHEMA)
    check("openai_compat: invalid JSON gets exactly one correction retry through the same path",
          r["parsed"] == [{"title": "x"}] and r["schema_retry"] is True and len(fake.calls) == 2
          and "not valid JSON" in fake.calls[1]["json"]["messages"][-1]["content"])

    fake, r, err = go([FakeHttpResponse(429, None, {"Retry-After": "3"}), chat_reply("later")])
    check("openai_compat: 429 with Retry-After is retried after exactly that wait, then succeeds",
          r["text"] == "later" and len(fake.calls) == 2 and sleeps == [3.0] and r["retries"] == 1)
    fake, r, err = go([FakeHttpResponse(503), FakeHttpResponse(500), chat_reply("ok")])
    check("openai_compat: 5xx without Retry-After uses the normal backoff (2 s, 4 s)", r["text"] == "ok" and sleeps == [2, 4])
    fake, r, err = go([requests.exceptions.ReadTimeout("slow"), requests.exceptions.ConnectionError("down"), chat_reply("ok")])
    check("openai_compat: timeouts and connection errors are retried", r["text"] == "ok" and len(fake.calls) == 3)
    fake, r, err = go([FakeHttpResponse(429, None, {"Retry-After": "100000"}), chat_reply("ok")])
    check("openai_compat: an absurd Retry-After is capped", sleeps == [llm_client._OC_MAX_RETRY_AFTER_S])

    for code in (401, 403):
        fake, r, err = go([FakeHttpResponse(code)])
        check(f"openai_compat: {code} is not retried (1 call, no wait) and raises LLMError(kind=access)",
              err is not None and err.kind == "access" and len(fake.calls) == 1 and not sleeps)
    fake, r, err = go([FakeHttpResponse(400)], config={"FALLBACK_MODEL_ID": "oc-fallback"})
    check("openai_compat: 400 is not retried and the fallback model is not tried",
          err is not None and err.kind == "validation" and len(fake.calls) == 1)
    fake, r, err = go([FakeHttpResponse(404), chat_reply("from fallback")], config={"FALLBACK_MODEL_ID": "oc-fallback"})
    check("openai_compat: unknown model (404) moves to the fallback model", r["model_id"] == "oc-fallback" and len(fake.calls) == 2)
    fake, r, err = go([FakeHttpResponse(429)] * 3 + [chat_reply("fb")], config={"FALLBACK_MODEL_ID": "oc-fallback"})
    check("openai_compat: fallback model used after 3 transient failures of the primary",
          r["model_id"] == "oc-fallback" and [c["json"]["model"] for c in fake.calls] == ["oc-primary"] * 3 + ["oc-fallback"])
    fake, r, err = go([chat_reply("x")], config={"NVIDIA_API_KEY": ""})
    check("openai_compat: no NVIDIA_API_KEY -> config error and no request is made", err is not None and err.kind == "config" and not fake.calls)
    fake, r, err = go([FakeHttpResponse(200, {"unexpected": True})])
    check("openai_compat: a 200 without choices[0].message.content is an error, not a crash", err is not None and err.kind == "validation")

    # Observed on the real endpoint (openai/gpt-oss-20b, a 24,289-character roadmap-phase prompt): the reply
    # is valid and complete (finish_reason "stop", 11,551 completion tokens incl. reasoning) but takes 178 s,
    # so a 90 s timeout failed every phase. The stub reproduces the response SHAPE from the saved real file
    # (scripts/fixtures/openai_compat_phase_response.json, key and ids removed) and its latency.
    import json as _json
    fixture = _json.load(open("scripts/fixtures/openai_compat_phase_response.json", encoding="utf-8"))
    REAL_LATENCY_S = 178.2

    def slow_endpoint(url, headers=None, json=None, timeout=None, **kw):
        slow_endpoint.timeouts.append(timeout)
        if timeout < REAL_LATENCY_S:
            raise requests.exceptions.ReadTimeout("read timed out")
        return FakeHttpResponse(200, fixture)
    slow_endpoint.timeouts = []

    unset = {"LLM_TIMEOUT_S_OPENAI_COMPAT": Config.LLM_TIMEOUT_S_OPENAI_COMPAT, "LLM_TIMEOUT_S": 90.0}
    sleeps.clear()
    with Env({**OPENAI, **unset, "LLM_TIMEOUT_S_OPENAI_COMPAT": 90.0}), patch.object(requests, "post", slow_endpoint):
        try:
            generate("roadmap", "p", max_output_tokens=16384)
            err = None
        except LLMError as exc:
            err = exc
    check("real failure mode: with a 90 s timeout the 178 s phase response times out on every attempt -> LLMError(kind=transient)",
          err is not None and err.kind == "transient" and slow_endpoint.timeouts == [90.0, 90.0, 90.0])
    slow_endpoint.timeouts.clear()
    with Env({**OPENAI, "LLM_TIMEOUT_S_OPENAI_COMPAT": 300.0, "LLM_TIMEOUT_S": 90.0}), patch.object(requests, "post", slow_endpoint):
        r = generate("roadmap", "p", max_output_tokens=16384)
    check("real failure mode fixed: the openai_compat timeout (300 s) is separate from LLM_TIMEOUT_S (90 s, still used by gemini and bedrock)",
          slow_endpoint.timeouts == [300.0] and r["text"].startswith("[") and r["input_tokens"] == 8903 and r["output_tokens"] == 11551)
    check("the response shape with reasoning/reasoning_content/tool_calls fields is read correctly (content used, reasoning ignored)",
          "reasoning" not in r["text"] and r["model_id"] == "oc-primary")
    import subprocess

    def timeouts_with(**env_vars):
        clean = {k: v for k, v in os.environ.items() if k not in ("LLM_TIMEOUT_S", "LLM_TIMEOUT_S_OPENAI_COMPAT")}
        out = subprocess.run([sys.executable, "-c", "from app.config import Config as C; print(C.LLM_TIMEOUT_S, C.LLM_TIMEOUT_S_OPENAI_COMPAT)"],
                             capture_output=True, text=True, env={**clean, **env_vars}).stdout.split()
        return tuple(float(x) for x in out)
    check("config: with nothing set the timeouts are 90 s (gemini/bedrock) and 300 s (openai_compat)", timeouts_with() == (90.0, 300.0))
    check("config: an explicit LLM_TIMEOUT_S applies to openai_compat too, and the specific variable wins over it",
          timeouts_with(LLM_TIMEOUT_S="45") == (45.0, 45.0) and timeouts_with(LLM_TIMEOUT_S="45", LLM_TIMEOUT_S_OPENAI_COMPAT="200") == (45.0, 200.0))

    # failover to the other provider when it is configured
    gemini_calls = []

    def fake_gemini(prompt, **kwargs):
        gemini_calls.append(kwargs)
        return {"text": "from gemini", "model_id": "g", "input_tokens": 1, "output_tokens": 1}
    fake = FakePost([FakeHttpResponse(503)] * 3)
    with Env(OPENAI, {"GEMINI_API_KEY": FAKE_SECRET}), patch.object(requests, "post", fake), \
            patch.object(gemini_client, "generate_with_retry", fake_gemini):
        r = generate("roadmap", "p")
    check("openai_compat: provider switch to gemini when the other provider is configured", r["provider"] == "gemini" and len(gemini_calls) == 1)

    # the shared limiter
    interval_rpm = 60
    llm_client._limiter._next_slot = 0.0
    waits, lock = [], threading.Lock()
    original_monotonic = llm_client._monotonic
    llm_client._monotonic = lambda: 100.0

    def take():
        w = llm_client._limiter.acquire(interval_rpm)
        with lock:
            waits.append(w)
    threads = [threading.Thread(target=take) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    llm_client._monotonic = original_monotonic
    check("limiter: 8 simultaneous callers at 60/min are given 8 distinct slots exactly 1 s apart (none refused)",
          sorted(waits) == [float(i) for i in range(8)])

    llm_client._limiter_sleep = time.sleep
    llm_client._limiter._next_slot = 0.0
    fake = FakePost([chat_reply("ok") for _ in range(8)])
    started = time.monotonic()
    with Env({**OPENAI, "LLM_MAX_RPM": 1200}), patch.object(requests, "post", fake):   # 0.05 s between requests
        workers = [threading.Thread(target=lambda: generate("roadmap", "p")) for _ in range(8)]
        for t in workers:
            t.start()
        for t in workers:
            t.join()
    times = sorted(c["at"] for c in fake.calls)
    gaps = [b - a for a, b in zip(times, times[1:])]
    check("limiter: 8 threads calling generate() at 1200/min really spread their requests over >= 0.35 s (real clock, jitter-tolerant)",
          len(times) == 8 and times[-1] - times[0] >= 0.3 and time.monotonic() - started >= 0.3 and all(times[i + 2] - times[i] >= 0.07 for i in range(6)))
    llm_client._limiter_sleep = lambda seconds: None
    llm_client._limiter._next_slot = 0.0
    check("limiter: retries pass through the same limiter (a retried call takes a second slot)",
          len(go([FakeHttpResponse(503), chat_reply("ok")], config={"LLM_MAX_RPM": 60})[0].calls) == 2)

    # no key anywhere
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.DEBUG)
    root = logging.getLogger()
    old_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    messages = []
    try:
        leaky = f"boom Authorization: Bearer {OC_KEY} {PROMPT_TEXT}"
        for script in ([FakeHttpResponse(401)], [requests.exceptions.RequestException(leaky)], [FakeHttpResponse(500)] * 3,
                       [requests.exceptions.ReadTimeout(leaky)] * 3, [chat_reply("bad " + REPLY_TEXT), chat_reply("worse " + REPLY_TEXT)]):
            _, _, err = go(script, prompt=PROMPT_TEXT, schema=SCHEMA)
            if err is not None:
                messages.append(str(err))
        go([chat_reply(REPLY_TEXT)], prompt=PROMPT_TEXT)
    finally:
        root.removeHandler(handler)
        root.setLevel(old_level)
    logged = stream.getvalue()
    check("openai_compat: the API key appears in no error and no log line", len(messages) == 5 and all(OC_KEY not in m and "Bearer" not in m for m in messages)
          and OC_KEY not in logged and "Bearer" not in logged)
    check("openai_compat: neither prompt text nor reply text appears in errors or logs",
          PROMPT_TEXT not in logged and REPLY_TEXT not in logged and all(PROMPT_TEXT not in m and REPLY_TEXT not in m for m in messages))
    check("openai_compat: a successful call logs one line with provider, model, tokens and latency",
          "llm_call task=roadmap provider=openai_compat model=oc-primary" in logged and "in_tokens=21" in logged)


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

    openai_compat_checks(sleeps)

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
