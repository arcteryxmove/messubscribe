# Точка входа: polling, middleware, планировщик, graceful shutdown
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import get_settings
from bot.database.engine import async_session_factory, engine, init_db
from bot.handlers import admin as admin_handlers
from bot.handlers import payment as payment_handlers
from bot.handlers import start as start_handlers
from bot.handlers import subscription as subscription_handlers
from bot.middlewares import DbSessionMiddleware, UpdateLoggingMiddleware
from bot.services.scheduler import build_scheduler

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    settings = get_settings()
    Path("logs").mkdir(parents=True, exist_ok=True)
    level = getattr(logging, settings.log_level, logging.INFO)
    fmt = "%(asctime)s %(levelname)s %(name)s %(message)s"
    root = logging.getLogger()
    root.setLevel(level)
    fh = logging.FileHandler(settings.log_file, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(logging.Formatter(fmt))
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(logging.Formatter(fmt))
    root.handlers.clear()
    root.addHandler(fh)
    root.addHandler(ch)


async def main() -> None:
    setup_logging()
    settings = get_settings()
    await init_db()
    bot = Bot(
        settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.outer_middleware(UpdateLoggingMiddleware())
    dp.update.middleware(DbSessionMiddleware(async_session_factory))

    dp.include_router(start_handlers.router)
    dp.include_router(payment_handlers.router)
    dp.include_router(subscription_handlers.router)
    dp.include_router(admin_handlers.router)

    scheduler = build_scheduler(bot, async_session_factory)
    scheduler.start()

    try:
        logger.info("Бот запущен")
        await dp.start_polling(bot)
    except Exception:
        logger.exception("Критическая ошибка polling")
        raise
    finally:
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            logger.exception("scheduler shutdown")
        try:
            await bot.session.close()
        except Exception:
            logger.exception("bot session close")
        try:
            await engine.dispose()
        except Exception:
            logger.exception("engine dispose")
        logger.info("Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())
