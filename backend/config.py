from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gemini_api_key: str = ""
    groq_api_key: str = ""
    tts_voice: str = "vi-VN-HoaiMyNeural"
    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    tiktok_redirect_uri: str = "http://localhost:8000/auth/tiktok/callback"
    data_dir: Path = Path("data/jobs")
    api_base_url: str = "http://localhost:8000"
    database_url: str = "sqlite+aiosqlite:///./data/attv.db"


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
