from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Google Gemini ──────────────────────────────────────────────────────
    gemini_api_key: str = Field(..., description="Google Gemini API key")
    gemini_model: str = "gemini-1.5-flash"
    embedding_model: str = "models/text-embedding-004"

    # ── Qdrant ────────────────────────────────────────────────────────────
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "agromind"

    # ── PostgreSQL / TimescaleDB ──────────────────────────────────────────
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "agromind"
    postgres_user: str = "agromind"
    postgres_password: str = "agromind_secret"
    postgres_url: str = "postgresql://agromind:agromind_secret@localhost:5432/agromind"

    # ── Redis ─────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Celery ────────────────────────────────────────────────────────────
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # ── MLflow ────────────────────────────────────────────────────────────
    mlflow_tracking_uri: str = "http://localhost:5000"
    mlflow_experiment_name: str = "agromind-eval"

    # ── LangSmith ─────────────────────────────────────────────────────────
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "agromind-ai"

    # ── Application ───────────────────────────────────────────────────────
    app_env: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # ── Ingestion ─────────────────────────────────────────────────────────
    data_dir: Path = Path("./data")
    raw_data_dir: Path = Path("./data/raw")
    max_crawl_retries: int = 3
    crawl_backoff_base: int = 2

    # ── Open-Meteo ────────────────────────────────────────────────────────
    openmeteo_base_url: str = "https://archive-api.open-meteo.com/v1/archive"
    weather_districts: str = (
        "Colombo,Kandy,Galle,Jaffna,Anuradhapura,Kurunegala,Ratnapura,Badulla,Trincomalee,Matara"
    )

    # ── Config paths ──────────────────────────────────────────────────────
    @property
    def config_dir(self) -> Path:
        return Path(__file__).parent

    @property
    def crops_yaml(self) -> Path:
        return self.config_dir / "crops.yaml"

    @property
    def districts_yaml(self) -> Path:
        return self.config_dir / "districts.yaml"

    @property
    def prompts_dir(self) -> Path:
        return self.config_dir / "prompts"

    @property
    def weather_district_list(self) -> list[str]:
        return [d.strip() for d in self.weather_districts.split(",")]


settings = Settings()
