# Telegram Payments + pre_checkout + successful_payment
from __future__ import annotations

import logging
import uuid
from typing import Optional, Tuple

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.database import crud
from bot.database.models import User
from bot.services import payment_service, subscription_service
from bot.texts import messages as T

logger = logging.getLogger(__name__)
router = Router(name="payment")


def _parse_payload(payload: str) -> Optional[Tuple[str, int]]:
    parts = payload.split(":", 1)
    if len(parts) != 2:
        return None
    kind, uid_s = parts
    try:
        return kind, int(uid_s)
    except ValueError:
        return None


async def process_successful_order(
    session: AsyncSession,
    bot: Bot,
    user: User,
    *,
    kind: str,
    payment_external_id: str,
    fetch_yookassa_method: bool = True,
) -> str:
    """
    Создаёт подписку и платёж в БД, возвращает HTML-текст для пользователя.
    kind: 'trial' | 'full'
    """
    settings = get_settings()
    if fetch_yookassa_method and settings.yookassa_configured:
        pm_id = await payment_service.fetch_payment_method_id(str(payment_external_id))
        if pm_id:
            await crud.update_user_payment_method(session, user.id, pm_id)

    if kind == "trial":
        sub = await crud.create_trial_subscription(
            session,
            user_id=user.id,
            days=settings.trial_days,
        )
        await crud.create_payment_succeeded(
            session,
            user_id=user.id,
            subscription_id=sub.id,
            amount=settings.trial_amount_kopecks,
            yookassa_payment_id=str(payment_external_id),
            is_trial=True,
        )
        link = await subscription_service.grant_access_invite_link(
            bot,
            settings.channel_id,
            user.telegram_id,
        )
        if link:
            return T.payment_success_trial(link)
        return T.payment_success_trial_already_in_channel()

    sub = await crud.activate_or_extend_subscription(
        session,
        user_id=user.id,
        period_days=settings.subscription_period_days,
    )
    await crud.create_payment_succeeded(
        session,
        user_id=user.id,
        subscription_id=sub.id,
        amount=settings.subscription_amount_kopecks,
        yookassa_payment_id=str(payment_external_id),
        is_trial=False,
    )
    link = await subscription_service.grant_access_invite_link(
        bot,
        settings.channel_id,
        user.telegram_id,
    )
    return T.payment_success_full(link)


@router.callback_query(F.data.in_(("pay_trial", "pay_full")))
async def cb_pay(query: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    settings = get_settings()
    try:
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

        is_trial = query.data == "pay_trial"
        if is_trial and await crud.has_used_trial_offer(session, user.id):
            await query.message.answer(T.trial_used_only_full())
            await query.answer()
            await session.commit()
            return

        # Без PAYMENTS_TOKEN — тот же сценарий, что после оплаты (для просмотра UX)
        if settings.use_mock_payments:
            kind = "trial" if is_trial else "full"
            mock_id = f"mock:{kind}:{user.id}:{uuid.uuid4().hex[:12]}"
            text = await process_successful_order(
                session,
                bot,
                user,
                kind=kind,
                payment_external_id=mock_id,
                fetch_yookassa_method=False,
            )
            if query.message:
                await query.message.answer(text)
            await query.answer()
            await session.commit()
            return

        if not settings.payments_configured:
            await query.message.answer(T.payments_not_configured())
            await query.answer()
            await session.commit()
            return

        if is_trial:
            amount = settings.trial_amount_kopecks
            title = T.invoice_title_trial()
            desc = T.invoice_description_trial()
            payload = f"trial:{user.id}"
        else:
            amount = settings.subscription_amount_kopecks
            title = T.invoice_title_full()
            desc = T.invoice_description_full()
            payload = f"full:{user.id}"

        if not query.message:
            await query.answer(T.error_generic(), show_alert=True)
            return
        try:
            await bot.send_invoice(
                chat_id=query.message.chat.id,
                title=title,
                description=desc,
                payload=payload,
                provider_token=settings.payments_token,
                currency="RUB",
                prices=[LabeledPrice(label=title, amount=amount)],
            )
        except TelegramBadRequest as e:
            logger.exception("send_invoice bad request")
            await query.message.answer(T.payment_invoice_error(str(e)))
            await query.answer()
            await session.commit()
            return
        await query.answer()
        await session.commit()
    except Exception:
        logger.exception("cb_pay")
        try:
            await session.rollback()
        except Exception:
            logger.exception("cb_pay rollback")
        details = None
        try:
            import traceback

            details = traceback.format_exc().splitlines()[-1]
        except Exception:
            details = None

        if query.message:
            await query.message.answer(T.payment_invoice_error(details))
            await query.answer()
        else:
            await query.answer(T.error_generic(), show_alert=True)


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery, session: AsyncSession) -> None:
    settings = get_settings()
    try:
        parsed = _parse_payload(query.invoice_payload)
        if not parsed:
            await query.answer(ok=False, error_message=T.pre_checkout_error())
            return
        kind, user_db_id = parsed
        if not query.from_user:
            await query.answer(ok=False, error_message=T.pre_checkout_error())
            return
        user = await session.get(User, user_db_id)
        if not user or user.telegram_id != query.from_user.id:
            await query.answer(ok=False, error_message=T.pre_checkout_error())
            return

        expected = (
            settings.trial_amount_kopecks
            if kind == "trial"
            else settings.subscription_amount_kopecks
        )
        if query.total_amount != expected:
            await query.answer(ok=False, error_message=T.pre_checkout_error())
            return

        if kind == "trial" and await crud.has_used_trial_offer(session, user.id):
            await query.answer(ok=False, error_message=T.pre_checkout_error())
            return

        await query.answer(ok=True)
    except Exception:
        logger.exception("pre_checkout")
        await query.answer(ok=False, error_message=T.pre_checkout_error())


@router.message(F.successful_payment)
async def successful_payment(message: Message, session: AsyncSession, bot: Bot) -> None:
    settings = get_settings()
    sp = message.successful_payment
    if not sp:
        return
    try:
        parsed = _parse_payload(sp.invoice_payload)
        if not parsed:
            await message.answer(T.error_generic())
            return
        kind, user_db_id = parsed
        user = await session.get(User, user_db_id)
        if not user or user.telegram_id != message.from_user.id:
            await message.answer(T.error_generic())
            return

        provider_pid = sp.provider_payment_charge_id or sp.telegram_payment_charge_id
        text = await process_successful_order(
            session,
            bot,
            user,
            kind=kind,
            payment_external_id=str(provider_pid),
            fetch_yookassa_method=True,
        )
        await message.answer(text)
        await session.commit()
    except Exception:
        logger.exception("successful_payment")
        await session.rollback()
        await message.answer(T.error_generic())
