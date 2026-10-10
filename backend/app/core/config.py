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
    # Was "2.0.0" — did not match the actual trained legacy model bundle
    # (training_report.json), .env.example, or render.yaml, all of which say
    # "1.0.0". Any environment without an explicit MODEL_VERSION override
    # (e.g. local/dev without .env) would misreport its own model version.
    # Fixed to match reality; render.yaml's explicit "1.0.0" override is
    # unchanged and continues to take precedence in production regardless.
    MODEL_VERSION: str = "1.0.0"

    # Which prediction pipeline serves /predictions/predict and
    # /tournament/simulate — see app/ml/model_loader.py and docs/ml/.
    #   "legacy" -> (default) the existing predictors: v1.0.0, or V2 when
    #               USE_V2_MODEL is true.
    #   "v3"     -> opt-in: app.ml.v3 (Elo + Poisson/Dixon-Coles + XGBoost
    #               blend, trained on the full international results corpus).
    # Any other value is treated as "legacy".
    PREDICTION_ENGINE: str = "legacy"

    # V2 model feature flag — see app/ml/model_loader.py. Only consulted when
    # PREDICTION_ENGINE is not "v3". Default MUST stay False.
    USE_V2_MODEL: bool = False
    # Which V2 bundle to serve when USE_V2_MODEL is on:
    #   True  -> v2_production_calibrated (trained through 2026, for predicting
    #            future matches). This is the correct choice for live serving.
    #   False -> v2_backtest_calibrated (frozen at 2022; only meaningful for
    #            reproducing the WC2026 backtest).
    V2_USE_PRODUCTION_MODEL: bool = True
    # Feature-engine data source. "supabase" reads matches_v2/teams_v2/
    # match_statistics_v2 and is the production default — a deployed container
    # must not depend on a local CSV. "csv" is the dev/offline fallback and the
    # reference the Supabase loader is verified against.
    V2_DATA_SOURCE: str = "supabase"

    # Rate limiting.
    # RATE_LIMIT_PER_MINUTE predates this and was never enforced anywhere; it
    # is kept so existing environments setting it don't break, but the two
    # per-endpoint limits below are what app/core/rate_limit.py actually uses.
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_ENABLED: bool = True
    # One request per form submission on the predict page; generous headroom
    # for a user exploring matchups, restrictive enough to stop bulk scraping.
    RATE_LIMIT_PREDICT_PER_MINUTE: int = 30
    # 5-9s of multi-process CPU per call, up to 100k iterations — a handful of
    # concurrent callers can saturate a starter instance, so this is far
    # stricter. Triggered by an explicit button press, never on page load.
    RATE_LIMIT_SIMULATE_PER_MINUTE: int = 5

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
