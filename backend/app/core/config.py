from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    APP_NAME: str = "FIFA AI Score Prediction API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # API
    API_V1_PREFIX: str = "/api/v1"
    # Dev-only default; production origins are supplied via the ALLOWED_ORIGINS
    # env var (see .env / render.yaml) as a JSON array, e.g.
    # ALLOWED_ORIGINS=["https://my-app.vercel.app"]
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    # Supabase
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_ANON_KEY: str

    # Database (direct connection for SQLAlchemy)
    DATABASE_URL: str

    # JWT (Supabase JWT secret for token verification)
    SUPABASE_JWT_SECRET: str

    # ML
    MODEL_PATH: str = "app/ml/models/xgboost_model.pkl"
    SCALER_PATH: str = "app/ml/models/scaler.pkl"
    FEATURE_IMPORTANCE_PATH: str = "app/ml/models/feature_importance.json"
    MODEL_VERSION: str = "2.0.0"

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
