# Выдача и отзыв доступа к закрытому каналу
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


async def create_single_use_invite(bot: Bot, channel_id: int) -> str:
    """Создаёт пригласительную ссылку с одним использованием."""
    if not channel_id or channel_id >= 0:
        raise ValueError("CHANNEL_ID не задан")
    link = await bot.create_chat_invite_link(
        chat_id=channel_id,
        name="messubscribe-single",
        creates_join_request=False,
        member_limit=1,
    )
    return link.invite_link


async def get_chat_member_status(
    bot: Bot,
    channel_id: int,
    user_id: int,
) -> Optional[str]:
    """Статус участника (member, left, admin, ...) или None при ошибке."""
    try:
        m = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return m.status
    except TelegramBadRequest as e:
        logger.warning("get_chat_member: %s", e)
        return None
    except Exception:
        logger.exception("get_chat_member")
        return None


async def user_in_channel(bot: Bot, channel_id: int, user_id: int) -> bool:
    st = await get_chat_member_status(bot, channel_id, user_id)
    if st is None:
        return False
    return st in ("member", "administrator", "creator", "restricted")


async def grant_access_invite_link(
    bot: Bot,
    channel_id: int,
    user_telegram_id: int,
) -> Optional[str]:
    """Если пользователь уже в канале — ссылка не обязательна; иначе возвращаем одноразовую."""
    if not channel_id or channel_id >= 0:
        return None
    if await user_in_channel(bot, channel_id, user_telegram_id):
        return None
    return await create_single_use_invite(bot, channel_id)


async def kick_from_channel(bot: Bot, channel_id: int, user_telegram_id: int) -> None:
    """Удаляет пользователя из канала."""
    if not channel_id or channel_id >= 0:
        return
    try:
        await bot.ban_chat_member(chat_id=channel_id, user_id=user_telegram_id)
        await bot.unban_chat_member(chat_id=channel_id, user_id=user_telegram_id)
    except TelegramBadRequest as e:
        logger.warning("kick_from_channel: %s", e)
    except Exception:
        logger.exception("kick_from_channel")
