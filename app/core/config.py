from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Family Finance Bot"
    environment: str = "local"
    database_url: str = "postgresql+asyncpg://finance:finance@localhost:5432/family_finance"
    telegram_bot_token: str = Field(default="", repr=False)
    openai_api_key: str = Field(default="", repr=False)
    llm_model: str = "gpt-4o-mini"
    stt_model: str = "whisper-1"
    default_currency: str = "RUB"
    admin_invite_code: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def model_post_init(self, __context: object) -> None:
        # Render and some PostgreSQL providers expose URLs as postgres://...
        # SQLAlchemy asyncpg expects postgresql+asyncpg://...
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
