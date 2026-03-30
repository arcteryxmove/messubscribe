# Конфигурация бота через pydantic-settings
from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Достаточно для простого запуска (остальное опционально)
    bot_token: str = Field(..., alias="BOT_TOKEN")

    yookassa_shop_id: str = Field(default="", alias="YOOKASSA_SHOP_ID")
    yookassa_secret_key: str = Field(default="", alias="YOOKASSA_SECRET_KEY")

    # 0 — канал не настроен (бот работает без выдачи ссылок в канал)
    channel_id: int = Field(default=0, alias="CHANNEL_ID")

    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/bot.db",
        alias="DATABASE_URL",
    )
    admin_ids: str = Field(default="", alias="ADMIN_IDS")
    payments_token: str = Field(default="", alias="PAYMENTS_TOKEN")

    # Нет PAYMENTS_TOKEN: при true — сразу показываем сценарий успешной оплаты (как в проде)
    mock_payments: bool = Field(default=True, alias="MOCK_PAYMENTS")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        alias="LOG_LEVEL",
    )
    log_file: str = Field(default="logs/bot.log", alias="LOG_FILE")

    trial_amount_kopecks: int = Field(default=100, alias="TRIAL_AMOUNT_KOPECKS")
    subscription_amount_kopecks: int = Field(
        default=29900,
        alias="SUBSCRIPTION_AMOUNT_KOPECKS",
    )
    trial_days: int = Field(default=3, alias="TRIAL_DAYS")
    subscription_period_days: int = Field(default=3, alias="SUBSCRIPTION_PERIOD_DAYS")
    grace_hours_after_failed_charge: int = Field(
        default=24,
        alias="GRACE_HOURS_AFTER_FAILED_CHARGE",
    )
    scheduler_interval_minutes: int = Field(
        default=30,
        alias="SCHEDULER_INTERVAL_MINUTES",
    )

    support_username: Optional[str] = Field(default=None, alias="SUPPORT_USERNAME")

    @field_validator("channel_id")
    @classmethod
    def channel_id_ok(cls, v: int) -> int:
        if v == 0:
            return 0
        if v > 0:
            raise ValueError("CHANNEL_ID должен быть отрицательным (канал) или 0")
        return v

    @property
    def admin_id_list(self) -> list[int]:
        raw = self.admin_ids.strip()
        if not raw:
            return []
        return [int(x.strip()) for x in raw.split(",") if x.strip()]

    @property
    def channel_configured(self) -> bool:
        return self.channel_id < 0

    @property
    def payments_configured(self) -> bool:
        return bool(self.payments_token.strip())

    @property
    def use_mock_payments(self) -> bool:
        """Нет PAYMENTS_TOKEN, но включён сценарий без реального invoice."""
        return self.mock_payments and not self.payments_configured

    @property
    def yookassa_configured(self) -> bool:
        return bool(self.yookassa_shop_id.strip() and self.yookassa_secret_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
