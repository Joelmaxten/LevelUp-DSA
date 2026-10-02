import os


def _env_flag(name, default):
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


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