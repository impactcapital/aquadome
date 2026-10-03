"""Runtime configuration via environment variables."""

from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AQUADOME_", env_file=".env", extra="ignore")

    # Database
    database_url: PostgresDsn = "postgresql+asyncpg://aquadome:aquadome@localhost:5432/aquadome"

    # Object storage (STAC imagery archive)
    s3_bucket: str = "aquadome-imagery"
    s3_endpoint_url: str | None = None  # set for MinIO / non-AWS

    # Detection
    detector_model: str = "rfdetr"          # rfdetr | rtdetr | yolox
    detector_device: str = "cuda"           # cuda | cpu
    detector_confidence_threshold: float = 0.4
    detector_altitude_tiling: bool = True   # altitude-aware tiling for small objects

    # Tracking
    tracker_algorithm: str = "botsort"      # botsort | ocsort | bytetrack

    # Re-ID
    reid_embedding_dim: int = 512
    reid_similarity_threshold: float = 0.75

    # OCR
    ocr_engine: str = "paddleocr"

    # Multi-tenancy
    tenant_isolation: bool = True

    # CJIS boundary: analytics tier must NEVER ingest CJI
    cjis_scope_guard: bool = True           # refuse requests carrying CJI fields

    # Chain-of-custody
    telemetry_hash_algorithm: str = "sha256"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_secret_key: str = "change-me-in-production"

    @field_validator("detector_model")
    @classmethod
    def _valid_detector(cls, v: str) -> str:
        allowed = {"rfdetr", "rtdetr", "yolox", "rtmdet"}
        if v not in allowed:
            raise ValueError(f"detector_model must be one of {allowed}")
        return v


settings = Settings()
