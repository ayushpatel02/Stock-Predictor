"""
App-wide configuration via pydantic-settings.
All values come from environment variables or .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "sqlite:///./stock_predictor.db"

    # Redis (optional — feature-flagged in cache.py)
    redis_url: str = ""

    # External APIs (all optional)
    finnhub_api_key: str = ""

    # Model storage
    models_dir: str = "models"

    # Prediction thresholds
    buy_threshold: float = 0.65
    sell_threshold: float = 0.35

    # Data fetch defaults
    default_period: str = "2y"
    default_interval: str = "1d"

    # App
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]


settings = Settings()
