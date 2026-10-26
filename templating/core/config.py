from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL
from pydantic import Field

ROOT = Path(__file__).resolve().parents[1]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "myuser"
    DB_PASSWORD: str = "mypassword"
    DB_NAME: str = "smart_traffic"
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "media"
    MINIO_SECURE: bool = False
    MAX_IMAGE_BYTES: int = 10 * 1024 * 1024
    MAX_VIDEO_BYTES: int = 50 * 1024 * 1024
    REDIS_URL: str = "redis://localhost:6379/0"
    SESSION_TTL_SECONDS: int = Field(default=86400, gt=0)
    SESSION_COOKIE_NAME: str = "session_id"
    SESSION_COOKIE_SECURE: bool = False

    @property
    def DATABASE_URL(self):
        return URL.create("postgresql+asyncpg", username=self.DB_USER,
                          password=self.DB_PASSWORD, host=self.DB_HOST,
                          port=self.DB_PORT, database=self.DB_NAME)

settings = Settings()
