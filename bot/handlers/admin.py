# Админ-панель (/admin)
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.database import crud
from bot.database.models import SubscriptionStatus
from bot.keyboards import inline as kb
from bot.texts import messages as T

logger = logging.getLogger(__name__)
router = Router(name="admin")


class AdminStates(StatesGroup):
    waiting_search = State()
    waiting_broadcast = State()


def _is_admin(uid: int) -> bool:
    return uid in get_settings().admin_id_list


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _start_of_today_utc() -> datetime:
    n = _utcnow()
    return n.replace(hour=0, minute=0, second=0, microsecond=0)


@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        await message.answer(T.admin_denied())
        return
    await state.clear()
    await message.answer(T.admin_menu(), reply_markup=kb.kb_admin())
    await session.commit()


@router.callback_query(F.data == "admin_stats")
async def admin_stats_cb(query: CallbackQuery, session: AsyncSession) -> None:
    if not query.from_user or not _is_admin(query.from_user.id):
        await query.answer(T.admin_denied(), show_alert=True)
        return
    try:
        active = await crud.count_active_like(session)
        trial = await crud.count_active_trials(session)
        expired = await crud.count_subscriptions_by_status(session, SubscriptionStatus.expired)
        now = _utcnow()
        rev_today = await crud.sum_payments_kopecks(session, since=_start_of_today_utc())
        rev_7 = await crud.sum_payments_kopecks(session, since=now - timedelta(days=7))
        rev_30 = await crud.sum_payments_kopecks(session, since=now - timedelta(days=30))
        text = T.admin_stats(active, trial, expired, rev_today, rev_7, rev_30)
        await query.message.edit_text(text, reply_markup=kb.kb_admin())
        await query.answer()
        await session.commit()
    except Exception:
        logger.exception("admin_stats")
        await session.rollback()
        await query.answer(T.error_generic(), show_alert=True)


@router.callback_query(F.data == "admin_search")
async def admin_search_cb(query: CallbackQuery, state: FSMContext) -> None:
    if not query.from_user or not _is_admin(query.from_user.id):
        await query.answer(T.admin_denied(), show_alert=True)
        return
    await state.set_state(AdminStates.waiting_search)
    await query.message.answer(T.admin_search_prompt())
    await query.answer()


@router.message(AdminStates.waiting_search, F.text)
async def admin_search_run(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        await state.clear()
        return
    try:
        users = await crud.search_users(session, q=message.text.strip())
        if not users:
            await message.answer(T.admin_search_empty())
            await session.commit()
            return
        u = users[0]
        text = T.admin_user_card(u.telegram_id, u.username, u.full_name, u.is_banned)
        await message.answer(text, reply_markup=kb.kb_admin_user_actions(u.telegram_id, u.is_banned))
        await state.clear()
        await session.commit()
    except Exception:
        logger.exception("admin_search_run")
        await session.rollback()
        await message.answer(T.error_generic())


@router.callback_query(F.data.startswith("admin_ban:"))
async def admin_ban_cb(query: CallbackQuery, session: AsyncSession) -> None:
    if not query.from_user or not _is_admin(query.from_user.id):
        await query.answer(T.admin_denied(), show_alert=True)
        return
    try:
        tid = int(query.data.split(":", 1)[1])
        u = await crud.get_user_by_telegram_id(session, tid)
        if not u:
            await query.answer(T.admin_user_not_found(), show_alert=True)
            return
        await crud.set_user_banned(session, u.id, True)
        await query.message.edit_reply_markup(reply_markup=kb.kb_admin_user_actions(tid, True))
        await query.answer(T.admin_ban_ok())
        await session.commit()
    except Exception:
        logger.exception("admin_ban")
        await session.rollback()
        await query.answer(T.error_generic(), show_alert=True)


@router.callback_query(F.data.startswith("admin_unban:"))
async def admin_unban_cb(query: CallbackQuery, session: AsyncSession) -> None:
    if not query.from_user or not _is_admin(query.from_user.id):
        await query.answer(T.admin_denied(), show_alert=True)
        return
    try:
        tid = int(query.data.split(":", 1)[1])
        u = await crud.get_user_by_telegram_id(session, tid)
        if not u:
            await query.answer(T.admin_user_not_found(), show_alert=True)
            return
        await crud.set_user_banned(session, u.id, False)
        await query.message.edit_reply_markup(reply_markup=kb.kb_admin_user_actions(tid, False))
        await query.answer(T.admin_unban_ok())
        await session.commit()
    except Exception:
        logger.exception("admin_unban")
        await session.rollback()
        await query.answer(T.error_generic(), show_alert=True)


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_cb(query: CallbackQuery, state: FSMContext) -> None:
    if not query.from_user or not _is_admin(query.from_user.id):
        await query.answer(T.admin_denied(), show_alert=True)
        return
    await state.set_state(AdminStates.waiting_broadcast)
    await query.message.answer(T.admin_broadcast_prompt())
    await query.answer()


@router.message(AdminStates.waiting_broadcast)
async def admin_broadcast_run(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    bot: Bot,
) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        await state.clear()
        return
    try:
        ids = await crud.list_telegram_ids_active_subscribers(session)
        sent = 0
        failed = 0
        for tid in ids:
            try:
                if message.text:
                    await bot.send_message(tid, message.text)
                else:
                    await bot.copy_message(
                        chat_id=tid,
                        from_chat_id=message.chat.id,
                        message_id=message.message_id,
                    )
                sent += 1
            except Exception:
                failed += 1
                logger.warning("broadcast fail to %s", tid)
        await message.answer(T.admin_broadcast_done(sent, failed))
        await state.clear()
        await session.commit()
    except Exception:
        logger.exception("admin_broadcast_run")
        await session.rollback()
        await message.answer(T.error_generic())


@router.message(Command("cancel"))
async def admin_cancel(message: Message, state: FSMContext) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return
    cur = await state.get_state()
    if not cur:
        return
    await state.clear()
    await message.answer(T.admin_fsm_reset())
