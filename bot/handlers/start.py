# /start и приветствие
from __future__ import annotations

import logging
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.database import crud
from bot.keyboards import inline as kb
from bot.texts import messages as T

logger = logging.getLogger(__name__)
router = Router(name="start")


async def _render_start(
    session: AsyncSession,
    *,
    telegram_id: int,
    username: Optional[str],
    full_name: str,
) -> tuple[str, object]:
    settings = get_settings()
    user = await crud.get_or_create_user(
        session,
        telegram_id=telegram_id,
        username=username,
        full_name=full_name,
    )
    if user.is_banned:
        return T.banned_message(), None

    sub = await crud.get_active_subscription(session, user.id)
    has_active = sub is not None
    trial_ok = not await crud.has_used_trial_offer(session, user.id)

    text = f"<b>{T.welcome_title()}</b>\n\n{T.welcome_body()}"
    if has_active:
        text = f"<b>{T.welcome_title()}</b>\n\n{T.welcome_has_subscription()}"

    if settings.use_mock_payments:
        text += T.welcome_reset_hint()

    markup = kb.kb_start_main(
        has_active=has_active,
        trial_available=trial_ok and not has_active,
    )
    return text, markup


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    try:
        uid = message.from_user.id if message.from_user else 0
        un = message.from_user.username if message.from_user else None
        fn = message.from_user.full_name if message.from_user else ""
        text, markup = await _render_start(
            session,
            telegram_id=uid,
            username=un,
            full_name=fn,
        )
        await message.answer(text, reply_markup=markup)
        await session.commit()
    except Exception:
        logger.exception("cmd_start")
        await session.rollback()
        await message.answer(T.error_generic())


@router.message(Command("reset"))
async def cmd_reset(message: Message, session: AsyncSession) -> None:
    """Сброс данных подписки в БД — повторить сценарий с /start (только без реального PAYMENTS_TOKEN)."""
    try:
        settings = get_settings()
        if not settings.use_mock_payments:
            await message.answer(T.reset_denied())
            await session.commit()
            return
        uid = message.from_user.id if message.from_user else 0
        user = await crud.get_user_by_telegram_id(session, uid)
        if not user:
            await message.answer(T.error_generic())
            return
        await crud.wipe_user_subscription_data(session, user.id)
        await message.answer(T.reset_done())
        await session.commit()
    except Exception:
        logger.exception("cmd_reset")
        await session.rollback()
        await message.answer(T.error_generic())


@router.callback_query(F.data == "back_start")
async def cb_back_start(query: CallbackQuery, session: AsyncSession) -> None:
    try:
        uid = query.from_user.id if query.from_user else 0
        un = query.from_user.username if query.from_user else None
        fn = query.from_user.full_name if query.from_user else ""
        text, markup = await _render_start(
            session,
            telegram_id=uid,
            username=un,
            full_name=fn,
        )
        await query.message.edit_text(text, reply_markup=markup)
        await query.answer()
        await session.commit()
    except Exception:
        logger.exception("back_start")
        await session.rollback()
        await query.answer(T.error_generic(), show_alert=True)
