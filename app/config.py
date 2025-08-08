# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    FITBIT_CLIENT_ID: str = "dev"
    FITBIT_CLIENT_SECRET: str = "dev"
    FITBIT_REDIRECT_URI: str = "http://localhost:8000/auth/callback"
    DATABASE_URL: str = "sqlite:///./dev.db"
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    PORT: int = 8000

    # pydantic v2 style config
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()

