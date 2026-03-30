# Логирование входящих апдейтов
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

logger = logging.getLogger("bot.updates")


class UpdateLoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Update):
            uid = event.update_id
            et = "unknown"
            if event.message:
                et = "message"
            elif event.callback_query:
                et = "callback_query"
            elif event.pre_checkout_query:
                et = "pre_checkout_query"
            logger.debug("update_id=%s type=%s", uid, et)
        return await handler(event, data)
