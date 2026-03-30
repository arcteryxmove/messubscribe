# Интеграция с ЮKassa (синхронный SDK в отдельном потоке)
from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Any, Optional

from yookassa import Configuration, Payment

from bot.config import get_settings

logger = logging.getLogger(__name__)


def _configure() -> None:
    s = get_settings()
    Configuration.account_id = s.yookassa_shop_id
    Configuration.secret_key = s.yookassa_secret_key


def _format_amount_rub(kopecks: int) -> str:
    return str(Decimal(kopecks) / Decimal(100))


async def fetch_payment_method_id(yookassa_payment_id: str) -> Optional[str]:
    """Пытается получить сохранённый payment_method_id по платежу ЮKassa."""
    if not get_settings().yookassa_configured:
        return None

    def _sync() -> Optional[str]:
        _configure()
        try:
            p = Payment.find_one(yookassa_payment_id)
            if isinstance(p, dict):
                pm = p.get("payment_method") or {}
            else:
                pm = getattr(p, "payment_method", None)
                if pm is not None and not isinstance(pm, dict):
                    pm = getattr(pm, "__dict__", {}) or {}
            if isinstance(pm, dict):
                pid = pm.get("id")
                if isinstance(pid, str) and pid:
                    return pid
            return None
        except Exception:
            logger.exception("Ошибка получения платежа ЮKassa: %s", yookassa_payment_id)
            return None

    return await asyncio.to_thread(_sync)


def _payment_to_dict(obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    pid = getattr(obj, "id", None)
    st = getattr(obj, "status", None)
    return {"id": pid, "status": st}


async def create_recurring_payment(
    *,
    amount_kopecks: int,
    payment_method_id: str,
    description: str,
    idempotence_key: str,
) -> dict[str, Any]:
    """Создание автосписания по сохранённому методу оплаты."""
    if not get_settings().yookassa_configured:
        raise RuntimeError("ЮKassa не настроена")

    def _sync() -> dict[str, Any]:
        _configure()
        body = {
            "amount": {"value": _format_amount_rub(amount_kopecks), "currency": "RUB"},
            "capture": True,
            "payment_method_id": payment_method_id,
            "description": description[:128],
        }
        return _payment_to_dict(Payment.create(body, idempotence_key))

    return await asyncio.to_thread(_sync)


async def get_payment_status(yookassa_payment_id: str) -> Optional[str]:
    """Статус платежа: pending, waiting_for_capture, succeeded, canceled, failed."""
    if not get_settings().yookassa_configured:
        return None

    def _sync() -> Optional[str]:
        _configure()
        try:
            p = Payment.find_one(yookassa_payment_id)
            if isinstance(p, dict):
                return p.get("status")
            st = getattr(p, "status", None)
            return str(st) if st is not None else None
        except Exception:
            logger.exception("Ошибка статуса платежа ЮKassa: %s", yookassa_payment_id)
            return None

    return await asyncio.to_thread(_sync)
