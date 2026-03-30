# Периодические задачи (APScheduler)
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.config import get_settings
from bot.database import crud
from bot.keyboards import inline as kb
from bot.services import payment_service, subscription_service
from bot.texts import messages as T

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _send_reminders(bot: Bot, session) -> None:
    subs = await crud.subscriptions_due_for_reminder(session, within_hours=24)
    for sub in subs:
        try:
            await bot.send_message(
                sub.user.telegram_id,
                T.reminder_24h(),
                reply_markup=kb.kb_renew_manual(),
            )
            await crud.set_reminder_sent(session, sub)
        except Exception:
            logger.exception("reminder user_id=%s", sub.user_id)
    if subs:
        await session.commit()


async def _process_recurring(bot: Bot, session) -> None:
    settings = get_settings()
    subs = await crud.subscriptions_need_recurring_charge(session)
    for sub in subs:
        user = sub.user
        if user.is_banned:
            continue
        amount = settings.subscription_amount_kopecks

        # Без ЮKassa или без сохранённого метода — только ручная оплата / grace
        if not user.yookassa_payment_method_id or not settings.yookassa_configured:
            try:
                await bot.send_message(
                    user.telegram_id,
                    T.charge_failed(),
                    reply_markup=kb.kb_pay_manual(),
                )
                await crud.set_grace_period(
                    session,
                    sub,
                    _utcnow() + timedelta(hours=settings.grace_hours_after_failed_charge),
                )
                await session.commit()
            except Exception:
                logger.exception("grace without method user_id=%s", user.id)
                await session.rollback()
            continue

        idem = str(uuid.uuid4())
        try:
            pay = await payment_service.create_recurring_payment(
                amount_kopecks=amount,
                payment_method_id=user.yookassa_payment_method_id,
                description="Продление подписки messubscribe",
                idempotence_key=idem,
            )
            yid = pay.get("id") if isinstance(pay, dict) else None
            status = pay.get("status") if isinstance(pay, dict) else None
            if not yid:
                raise RuntimeError("Нет id платежа ЮKassa")

            db_pay = await crud.create_pending_payment(
                session,
                user_id=user.id,
                subscription_id=sub.id,
                amount=amount,
                yookassa_payment_id=str(yid),
                is_trial=False,
            )

            if status != "succeeded":
                status = await payment_service.get_payment_status(str(yid))

            if status == "succeeded":
                await crud.mark_payment_succeeded(session, db_pay.id)
                await crud.extend_subscription_after_charge(
                    session,
                    sub,
                    settings.subscription_period_days,
                )
                await session.commit()
                await bot.send_message(user.telegram_id, T.auto_renew_success())
            else:
                await crud.mark_payment_failed(session, db_pay.id)
                await crud.set_grace_period(
                    session,
                    sub,
                    _utcnow() + timedelta(hours=settings.grace_hours_after_failed_charge),
                )
                await session.commit()
                await bot.send_message(
                    user.telegram_id,
                    T.charge_failed(),
                    reply_markup=kb.kb_pay_manual(),
                )
        except Exception:
            logger.exception("Ошибка автосписания user_id=%s", user.id)
            await session.rollback()
            try:
                await crud.set_grace_period(
                    session,
                    sub,
                    _utcnow() + timedelta(hours=settings.grace_hours_after_failed_charge),
                )
                await session.commit()
            except Exception:
                logger.exception("grace after error")
            try:
                await bot.send_message(
                    user.telegram_id,
                    T.charge_failed(),
                    reply_markup=kb.kb_pay_manual(),
                )
            except Exception:
                logger.exception("notify charge failed")


async def _kick_grace_expired(bot: Bot, session) -> None:
    settings = get_settings()
    subs = await crud.subscriptions_past_grace(session)
    for sub in subs:
        try:
            await subscription_service.kick_from_channel(
                bot,
                settings.channel_id,
                sub.user.telegram_id,
            )
            await crud.expire_subscription(session, sub)
            await bot.send_message(sub.user.telegram_id, T.kicked_expired())
        except Exception:
            logger.exception("kick grace user_id=%s", sub.user_id)
    if subs:
        await session.commit()


async def _kick_cancelled_expired(bot: Bot, session) -> None:
    settings = get_settings()
    subs = await crud.cancelled_subscriptions_to_close(session)
    for sub in subs:
        try:
            await subscription_service.kick_from_channel(
                bot,
                settings.channel_id,
                sub.user.telegram_id,
            )
            await crud.expire_subscription(session, sub)
            await bot.send_message(sub.user.telegram_id, T.subscription_ended_no_renew())
        except Exception:
            logger.exception("kick cancelled user_id=%s", sub.user_id)
    if subs:
        await session.commit()


def build_scheduler(
    bot: Bot,
    session_factory: async_sessionmaker,
) -> AsyncIOScheduler:
    settings = get_settings()
    scheduler = AsyncIOScheduler(timezone="UTC")

    async def tick() -> None:
        async with session_factory() as session:
            try:
                await _send_reminders(bot, session)
            except Exception:
                logger.exception("tick reminders")
            try:
                await _process_recurring(bot, session)
            except Exception:
                logger.exception("tick recurring")
            try:
                await _kick_grace_expired(bot, session)
            except Exception:
                logger.exception("tick kick grace")
            try:
                await _kick_cancelled_expired(bot, session)
            except Exception:
                logger.exception("tick kick cancelled")

    scheduler.add_job(
        tick,
        "interval",
        minutes=settings.scheduler_interval_minutes,
        id="subscription_tick",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=120,
    )
    return scheduler
