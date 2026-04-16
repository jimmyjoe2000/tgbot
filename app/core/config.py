from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="Telegram Command Center", alias="APP_NAME")
    environment: Literal["development", "staging", "production"] = Field(
        default="development", alias="ENVIRONMENT"
    )
    debug: bool = Field(default=True, alias="DEBUG")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_prefix: str = Field(default="/api/v1", alias="API_PREFIX")
    admin_api_token: str = Field(default="change-me-admin-token", alias="ADMIN_API_TOKEN")

    postgres_server: str = Field(default="db", alias="POSTGRES_SERVER")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="telegram_center", alias="POSTGRES_DB")
    postgres_user: str = Field(default="telegram_center", alias="POSTGRES_USER")
    postgres_password: str = Field(default="change-me", alias="POSTGRES_PASSWORD")

    redis_host: str = Field(default="redis", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db: int = Field(default=0, alias="REDIS_DB")

    timezone: str = Field(default="Asia/Shanghai", alias="TIMEZONE")

    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_admin_user_id: int | None = Field(default=None, alias="TELEGRAM_ADMIN_USER_ID")
    telegram_polling_enabled: bool = Field(default=True, alias="TELEGRAM_POLLING_ENABLED")

    cloudflare_api_token: str = Field(default="", alias="CLOUDFLARE_API_TOKEN")
    cloudflare_api_base: str = Field(
        default="https://api.cloudflare.com/client/v4", alias="CLOUDFLARE_API_BASE"
    )

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="", alias="OPENAI_MODEL")
    dashscope_api_key: str = Field(default="", alias="DASHSCOPE_API_KEY")
    dashscope_model: str = Field(default="", alias="DASHSCOPE_MODEL")

    deploy_ssh_private_key_path: str = Field(
        default="/run/secrets/deploy_key", alias="DEPLOY_SSH_PRIVATE_KEY_PATH"
    )
    deploy_ssh_password: str = Field(default="", alias="DEPLOY_SSH_PASSWORD")
    deploy_default_ssh_user: str = Field(default="root", alias="DEPLOY_DEFAULT_SSH_USER")
    deploy_default_ssh_port: int = Field(default=22, alias="DEPLOY_DEFAULT_SSH_PORT")

    payment_provider_name: str = Field(default="", alias="PAYMENT_PROVIDER_NAME")
    payment_provider_base_url: str = Field(default="", alias="PAYMENT_PROVIDER_BASE_URL")
    payment_provider_api_key: str = Field(default="", alias="PAYMENT_PROVIDER_API_KEY")
    usdt_receive_address: str = Field(default="", alias="USDT_RECEIVE_ADDRESS")
    usdt_network: str = Field(default="TRON", alias="USDT_NETWORK")
    usdt_confirmations: int = Field(default=1, alias="USDT_CONFIRMATIONS")

    scheduler_hour: int = Field(default=0, alias="SCHEDULER_HOUR")
    scheduler_minute: int = Field(default=10, alias="SCHEDULER_MINUTE")

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_server}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
