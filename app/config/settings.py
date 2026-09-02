from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    bot_token: str = ""

    openrouter_api_key: str = ""

    openrouter_model: str = ""

    openrouter_fallback_model: str = ""

    database_url: str = "sqlite+aiosqlite:///./data/sara.db"

    admin_ids: str = ""

    timezone: str = "Asia/Tashkent"

    memory_enabled: bool = True

    proactive_group_mode: bool = True

    reminder_enabled: bool = True

    bot_to_bot_mode: bool = True

    media_enabled: bool = True

    max_recent_messages: int = 100

    max_memory_results: int = 15

    max_context_tokens: int = 12000

    proactive_cooldown_seconds: int = 300

    quiet_group_interval_seconds: int = 3600

    max_bot_chain: int = 5

    bot_to_bot_cooldown_seconds: int = 30

    user_rate_limit_seconds: float = 1.0

    group_rate_limit_seconds: float = 1.0

    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
