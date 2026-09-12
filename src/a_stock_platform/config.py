import os
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        self.database_url = os.getenv(
            "DATABASE_URL", f"sqlite:///{Path('data/platform.db')}"
        )
        self.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")
        self.session_ttl_seconds = int(os.getenv("SESSION_TTL_SECONDS", "86400"))
        self.live_data_enabled = os.getenv("LIVE_DATA_ENABLED", "true").lower() != "false"
        self.request_timeout_seconds = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "10"))


settings = Settings()
