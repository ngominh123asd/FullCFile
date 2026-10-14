"""
FileForge Backend - Core Configuration
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Literal


class Settings(BaseSettings):
    """Application settings"""

    # App
    APP_NAME: str = "FileForge"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = True
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/fileforge"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # S3 Storage
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "fileforge"
    S3_REGION: str = "us-east-1"

    # JWT
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # File Limits
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
    ALLOWED_EXTENSIONS: list[str] = [
        # Documents
        "md", "html", "pdf", "txt", "rtf", "docx", "doc",
        # Spreadsheets
        "csv", "xlsx", "xls", "ods", "json",
        # Images (for OCR)
        "png", "jpg", "jpeg", "webp", "tiff", "bmp", "gif",
        # Presentations
        "pptx",
    ]

    # OCR & Fine-Tuning Weights Settings
    OCR_LANGUAGES: list[str] = ["en", "vi"]
    OCR_MODEL_DIR: str = "/tmp/ocr_models"
    OCR_DET_THRESH: float = 0.3
    OCR_DET_BOX_THRESH: float = 0.5
    OCR_DET_UNCLIP_RATIO: float = 1.6
    OCR_REC_SCORE_THRESH: float = 0.5
    OCR_CLS_THRESH: float = 0.9
    OCR_MAX_SIDE_LEN: int = 1536
    OCR_DET_MODEL_PATH: str | None = None
    OCR_REC_MODEL_PATH: str | None = None
    OCR_CLS_MODEL_PATH: str | None = None
    OCR_REC_KEYS_PATH: str | None = None

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
    ]

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
