import os


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

    # External API keys — placeholders, fill via environment variables
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    ADZUNA_APP_ID = os.environ.get("ADZUNA_APP_ID", "")
    ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY", "")
    YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

    # Piston (self-hosted code execution)
    PISTON_API_URL = os.environ.get("PISTON_API_URL", "http://localhost:2000/api/v2/execute")

    # FAISS
    FAISS_INDEX_PATH = os.environ.get("FAISS_INDEX_PATH", "data/processed/faiss_index")


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}