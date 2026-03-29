import os
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    data_dir: Path = Path(os.getenv("DATA_DIR", "."))
    web_host: str = os.getenv("WEB_HOST", "0.0.0.0")
    web_port: int = int(os.getenv("WEB_PORT", "8000"))
    login_key: str = os.getenv("LOGIN_KEY", "admin123")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = os.getenv("LOG_LEVEL", "INFO")
    timezone: str = os.getenv("TIMEZONE", "Asia/Shanghai")

    model_config = {"extra": "ignore"}


settings = Settings()
