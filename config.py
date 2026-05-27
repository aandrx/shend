from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    bot_token: str
    base_url: str
    storage_path: Path = Path("./storage")
    data_path: Path = Path("./data")
    max_storage_gb: float = 20.0
    max_upload_mb: int = 500
    target_compress_mb: float = 9.5
    rate_limit_per_hour: int = 3

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Ensure directories exist at import time
settings.storage_path.mkdir(parents=True, exist_ok=True)
(settings.storage_path / "uploads").mkdir(exist_ok=True)
(settings.storage_path / "archive").mkdir(exist_ok=True)
(settings.storage_path / "temp").mkdir(exist_ok=True)
settings.data_path.mkdir(parents=True, exist_ok=True)
