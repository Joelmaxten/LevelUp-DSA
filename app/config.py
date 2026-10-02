import os


def _env_flag(name, default):
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _env_number(name, default, cast):
    """cast(os.environ[name]), or default when the variable is unset or empty (as in .env.example)."""
    value = os.environ.get(name)
    return default if value is None or value.strip() == "" else cast(value)


# SECRET_KEY values that must never reach production (the dev default, and the
# placeholder shipped in .env.example).
INSECURE_SECRET_KEYS = {"", "dev-secret-key-change-me", "change-me-to-a-random-string", "changeme", "secret"}


class Config:
    """Base configuration — values are pulled from environment variables.
    Never hardcode secrets here. Use a local .env file (gitignored) for dev.
    """

    # Flask
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql://localhost/levelup_dsa_dev",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session cookie. Secure is off in development (plain http://localhost) and
    # on in production; SESSION_COOKIE_SECURE=true/false overrides either.
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = _env_flag("SESSION_COOKIE_SECURE", False)

    # Usage limits (per user). The roadmap cap is a rolling window over
    # GeneratedRoadmap.created_at; the other two are in-process counters.
    ROADMAP_DAILY_LIMIT = int(os.environ.get("ROADMAP_DAILY_LIMIT", "5"))
    RESUME_UPLOAD_LIMIT_PER_HOUR = int(os.environ.get("RESUME_UPLOAD_LIMIT_PER_HOUR", "10"))
    RESUME_LISTINGS_LIMIT_PER_HOUR = int(os.environ.get("RESUME_LISTINGS_LIMIT_PER_HOUR", "30"))

    # External API keys — placeholders, fill via environment variables
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    ADZUNA_APP_ID = os.environ.get("ADZUNA_APP_ID", "")
    ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY", "")
    YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

    # LLM provider and models (see app/pipeline/llm_client.py). LLM_PROVIDER is
    # "gemini" (default) or "bedrock". The three model IDs are per task; left
    # empty, the gemini provider uses gemini_client's built-in models and the
    # bedrock provider refuses to run (it has no sensible default). Bedrock
    # reads AWS_REGION here and its credentials (AWS_BEARER_TOKEN_BEDROCK or
    # the normal AWS chain) from the environment, never from this file.
    LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "gemini").strip().lower() or "gemini"
    ROADMAP_MODEL_ID = os.environ.get("ROADMAP_MODEL_ID", "").strip()
    FAST_MODEL_ID = os.environ.get("FAST_MODEL_ID", "").strip()
    FALLBACK_MODEL_ID = os.environ.get("FALLBACK_MODEL_ID", "").strip()
    # Model to use if the OTHER provider has to take over after the first one fails.
    ALT_PROVIDER_MODEL_ID = os.environ.get("ALT_PROVIDER_MODEL_ID", "").strip()
    AWS_REGION = os.environ.get("AWS_REGION", "").strip()
    # LLM_PROVIDER="openai_compat": any OpenAI-compatible chat-completions endpoint (default: NVIDIA's).
    # The key is only ever sent as a bearer header by llm_client; it is never logged or put in an error.
    LLM_BASE_URL = (os.environ.get("LLM_BASE_URL", "").strip() or "https://integrate.api.nvidia.com/v1").rstrip("/")
    NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "").strip()
    # Client-side cap on requests per minute for that provider, shared by every thread in the process.
    LLM_MAX_RPM = max(1, _env_number("LLM_MAX_RPM", 30, int))
    # {model_id: {"input": usd_per_million_tokens, "output": usd_per_million_tokens}}.
    # Deliberately EMPTY: prices are never guessed, so cost shows as "unknown"
    # until you fill in the real figures for the models you use.
    PRICE_PER_MTOK = {}

    # Seconds before a single LLM request is abandoned (every provider, every task).
    LLM_TIMEOUT_S = _env_number("LLM_TIMEOUT_S", 90.0, float)
    # How many roadmap phases are written by the LLM at the same time. 1 = one after
    # another, exactly the original behavior. See roadmap_generator.generate_roadmap.
    PHASE_CONCURRENCY = max(1, _env_number("PHASE_CONCURRENCY", 1, int))
    # Two steps in different roadmap phases whose titles have at least this cosine similarity
    # (or equal titles) count as duplicates; the later phase is rewritten once. 0.80 was
    # measured on the saved real roadmaps (scripts/measure_duplicate_threshold.py).
    DUPLICATE_SIMILARITY_THRESHOLD = _env_number("DUPLICATE_SIMILARITY_THRESHOLD", 0.80, float)
    # Load the embedding model and the FAISS index in a background thread when the
    # server starts (run.py), so the first roadmap request doesn't pay ~20 s for it.
    WARMUP_ON_START = _env_flag("WARMUP_ON_START", True)

    # Piston (self-hosted code execution)
    PISTON_API_URL = os.environ.get("PISTON_API_URL", "http://localhost:2000/api/v2/execute")

    # FAISS
    FAISS_INDEX_PATH = os.environ.get("FAISS_INDEX_PATH", "data/processed/faiss_index")

    # Resume uploads
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads/resumes")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB - resumes are small; rejects oversized uploads at the Flask level before our code even runs


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = _env_flag("SESSION_COOKIE_SECURE", True)

    @classmethod
    def validate(cls):
        """Called at startup; refuses to boot production with a missing/default SECRET_KEY."""
        key = os.environ.get("SECRET_KEY", "")
        if key.strip().lower() in INSECURE_SECRET_KEYS or len(key) < 16:
            raise RuntimeError(
                "Refusing to start in production: SECRET_KEY is missing, a default/placeholder, "
                "or shorter than 16 characters. Set a long random SECRET_KEY in the environment."
            )


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}