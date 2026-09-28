from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

ROOT = Path(__file__).resolve().parents[1]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "myuser"
    DB_PASSWORD: str = "mypassword"
    DB_NAME: str = "smart_traffic"
    CURRENT_USER_ID: int = 1

    @property
    def DATABASE_URL(self):
        return URL.create("postgresql+asyncpg", username=self.DB_USER,
                          password=self.DB_PASSWORD, host=self.DB_HOST,
                          port=self.DB_PORT, database=self.DB_NAME)

settings = Settings()
