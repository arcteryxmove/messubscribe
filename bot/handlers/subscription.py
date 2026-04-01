# Кабинет и отмена подписки
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.database import crud
from bot.database.models import SubscriptionStatus
from bot.keyboards import inline as kb
from bot.texts import messages as T

logger = logging.getLogger(__name__)
router = Router(name="subscription")


def _status_label(status: SubscriptionStatus) -> str:
    return {
        SubscriptionStatus.trial: "Пробный период",
        SubscriptionStatus.active: "Активна",
        SubscriptionStatus.cancelled: "Активна (без автопродления)",
        SubscriptionStatus.expired: "Истекла",
    }.get(status, status.value)


async def _send_cabinet(message: Message, session: AsyncSession) -> None:
    uid = message.from_user.id if message.from_user else 0
    un = message.from_user.username if message.from_user else None
    fn = message.from_user.full_name if message.from_user else ""
    user = await crud.get_or_create_user(
        session,
        telegram_id=uid,
        username=un,
        full_name=fn,
    )
    if user.is_banned:
        await message.answer(T.banned_message())
        await session.commit()
        return

    sub = await crud.get_active_subscription(session, user.id)
    if not sub:
        await message.answer(T.cabinet_no_subscription())
        await session.commit()
        return

    text = (
        f"<b>{T.cabinet_header()}</b>\n\n"
        + T.cabinet_status(
            _status_label(sub.status),
            sub.expires_at,
            sub.next_charge_at,
        )
    )
    await message.answer(text, reply_markup=kb.kb_cabinet())
    await session.commit()


@router.message(Command("cabinet"))
async def cmd_cabinet(message: Message, session: AsyncSession) -> None:
    try:
        await _send_cabinet(message, session)
    except Exception:
        logger.exception("cmd_cabinet")
        await session.rollback()
        await message.answer(T.error_generic())


@router.callback_query(F.data == "cabinet")
async def cb_cabinet(query: CallbackQuery, session: AsyncSession) -> None:
    try:
        msg = query.message
        if not msg:
            await query.answer()
            return
        uid = query.from_user.id if query.from_user else 0
        un = query.from_user.username if query.from_user else None
        fn = query.from_user.full_name if query.from_user else ""
        user = await crud.get_or_create_user(
            session,
            telegram_id=uid,
            username=un,
            full_name=fn,
        )
        if user.is_banned:
            await query.answer(T.banned_message(), show_alert=True)
            return

        sub = await crud.get_active_subscription(session, user.id)
        if not sub:
            await msg.edit_text(T.cabinet_no_subscription())
            await query.answer()
            await session.commit()
            return

        text = (
            f"<b>{T.cabinet_header()}</b>\n\n"
            + T.cabinet_status(
                _status_label(sub.status),
                sub.expires_at,
                sub.next_charge_at,
            )
        )
        await msg.edit_text(text, reply_markup=kb.kb_cabinet())
        await query.answer()
        await session.commit()
    except Exception:
        logger.exception("cb_cabinet")
        await session.rollback()
        await query.answer(T.error_generic(), show_alert=True)


@router.callback_query(F.data == "cancel_sub_confirm")
async def cb_cancel_confirm(query: CallbackQuery, session: AsyncSession) -> None:
    try:
        msg = query.message
        if not msg:
            await query.answer()
            return
        await msg.edit_text(T.cancel_confirm(), reply_markup=kb.kb_cancel_confirm())
        await query.answer()
    except Exception:
        logger.exception("cancel_sub_confirm")
        await query.answer(T.error_generic(), show_alert=True)


@router.callback_query(F.data == "cancel_sub_no")
async def cb_cancel_no(query: CallbackQuery, session: AsyncSession) -> None:
    try:
        await cb_cabinet(query, session)
    except Exception:
        logger.exception("cancel_sub_no")
        await query.answer(T.error_generic(), show_alert=True)


@router.callback_query(F.data == "cancel_sub_yes")
async def cb_cancel_yes(query: CallbackQuery, session: AsyncSession) -> None:
    try:
        msg = query.message
        if not msg:
            await query.answer()
            return
        uid = query.from_user.id if query.from_user else 0
        user = await crud.get_user_by_telegram_id(session, uid)
        if not user:
            await query.answer()
            return
        sub = await crud.get_active_subscription(session, user.id)
        if sub:
            await crud.cancel_subscription_user(session, sub)
        await crud.update_user_payment_method(session, user.id, None)
        await msg.edit_text(T.cancel_done())
        await query.answer()
        await session.commit()
    except Exception:
        logger.exception("cancel_sub_yes")
        await session.rollback()
        await query.answer(T.error_generic(), show_alert=True)


@router.callback_query(F.data == "support")
async def cb_support(query: CallbackQuery, session: AsyncSession) -> None:
    settings = get_settings()
    try:
        un = settings.support_username
        text = T.support_message(un)
        await query.message.answer(text)
        await query.answer()
        await session.commit()
    except Exception:
        logger.exception("support")
        await session.rollback()
        await query.answer(T.error_generic(), show_alert=True)
