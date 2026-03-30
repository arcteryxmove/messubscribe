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
from bot.database.models import PaymentStatus
from bot.database.models import User
from bot.keyboards import inline as kb
from bot.services import payment_service, subscription_service
from bot.texts import messages as T

logger = logging.getLogger(__name__)
router = Router(name="payment")


def _error_details(exc: Exception) -> str:
    text = f"{exc.__class__.__name__}: {exc}"
    orig = getattr(exc, "orig", None)
    if orig:
        text = f"{text} | orig={orig}"
    return text


def _parse_payload(payload: str) -> Optional[Tuple[str, int]]:
    parts = payload.split(":", 1)
    if len(parts) != 2:
        return None
    kind, uid_s = parts
    # Поддержка payload вида "kind:tg:<id>"
    if uid_s.startswith("tg:"):
        uid_s = uid_s[3:]
    try:
        return kind, int(uid_s)
    except ValueError:
        return None


def _effective_trial_amount(settings) -> int:
    """
    Для реального Telegram Payments часть провайдеров/режимов не принимает 1 ₽.
    Если платежи реальные, поднимаем trial до минимально безопасной суммы 10 ₽.
    """
    if settings.payments_configured and settings.trial_amount_kopecks < 1000:
        return 1000
    return settings.trial_amount_kopecks


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
            amount=_effective_trial_amount(settings),
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
        is_trial = query.data == "pay_trial"

        user: Optional[User] = None
        # Важный момент: если БД недоступна/схема не совпала, не блокируем открытие invoice.
        try:
            user = await crud.get_or_create_user(
                session,
                telegram_id=uid,
                username=un,
                full_name=fn,
            )
            if user.is_banned:
                await query.answer(T.banned_message(), show_alert=True)
                return

            if is_trial and await crud.has_used_trial_offer(session, user.id):
                await query.message.answer(T.trial_used_only_full())
                await query.answer()
                await session.commit()
                return
        except Exception:
            logger.exception("db checks failed in cb_pay; continue with invoice")
            try:
                await session.rollback()
            except Exception:
                logger.exception("cb_pay rollback after db checks failure")

        # Без PAYMENTS_TOKEN — тот же сценарий, что после оплаты (для просмотра UX)
        if settings.use_mock_payments:
            if not user:
                user = await crud.get_or_create_user(
                    session,
                    telegram_id=uid,
                    username=un,
                    full_name=fn,
                )
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
            amount = _effective_trial_amount(settings)
            title = T.invoice_title_trial()
            desc = T.invoice_description_trial()
            payload = f"trial:tg:{uid}"
        else:
            amount = settings.subscription_amount_kopecks
            title = T.invoice_title_full()
            desc = T.invoice_description_full()
            payload = f"full:tg:{uid}"

        if not query.message:
            await query.answer(T.error_generic(), show_alert=True)
            return
        try:
            # Внешний сценарий: создаём redirect-платёж ЮKassa и отдаём ссылку.
            checkout = await payment_service.create_checkout_payment(
                amount_kopecks=amount,
                description=desc,
                user_telegram_id=uid,
                kind="trial" if is_trial else "full",
                return_url="https://t.me",
            )
            yid = str(checkout.get("id") or "")
            confirmation_url = str(checkout.get("confirmation_url") or "")
            if not yid or not confirmation_url:
                raise RuntimeError("ЮKassa не вернула id/confirmation_url")
            if user:
                await crud.create_pending_payment(
                    session,
                    user_id=user.id,
                    subscription_id=None,
                    amount=amount,
                    yookassa_payment_id=yid,
                    is_trial=is_trial,
                )
            await query.message.answer(
                T.yookassa_checkout_prompt(),
                reply_markup=kb.kb_yookassa_checkout(confirmation_url, yid),
            )
        except TelegramBadRequest as e:
            logger.exception("send_invoice bad request")
            await query.message.answer(T.payment_invoice_error(_error_details(e)))
            await query.answer()
            await session.commit()
            return
        except Exception as e:
            logger.exception("create checkout payment failed")
            await query.message.answer(T.payment_invoice_error(_error_details(e)))
            await query.answer()
            await session.commit()
            return
        await query.answer()
        await session.commit()
    except Exception as e:
        logger.exception("cb_pay")
        try:
            await session.rollback()
        except Exception:
            logger.exception("cb_pay rollback")
        details = _error_details(e)

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
        kind, telegram_id = parsed
        if not query.from_user:
            await query.answer(ok=False, error_message=T.pre_checkout_error())
            return
        if telegram_id != query.from_user.id:
            await query.answer(ok=False, error_message=T.pre_checkout_error())
            return

        expected = (
            _effective_trial_amount(settings)
            if kind == "trial"
            else settings.subscription_amount_kopecks
        )
        if query.total_amount != expected:
            await query.answer(ok=False, error_message=T.pre_checkout_error())
            return

        # Проверка trial по БД (если БД временно недоступна — не блокируем pre-checkout)
        if kind == "trial":
            try:
                user = await crud.get_user_by_telegram_id(session, telegram_id)
                if user and await crud.has_used_trial_offer(session, user.id):
                    await query.answer(ok=False, error_message=T.pre_checkout_error())
                    return
            except Exception:
                logger.exception("pre_checkout trial check failed; skip")

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
        kind, telegram_id = parsed
        if telegram_id != message.from_user.id:
            await message.answer(T.error_generic())
            return
        user = await crud.get_or_create_user(
            session,
            telegram_id=telegram_id,
            username=message.from_user.username if message.from_user else None,
            full_name=message.from_user.full_name if message.from_user else "",
        )

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


@router.callback_query(F.data.startswith("check_pay:"))
async def cb_check_payment(query: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    try:
        if not query.from_user:
            await query.answer()
            return
        yid = query.data.split(":", 1)[1]
        user = await crud.get_user_by_telegram_id(session, query.from_user.id)
        if not user:
            await query.answer(T.payment_check_failed(), show_alert=True)
            return
        pay = await crud.get_payment_by_yookassa_id(session, yid)
        if not pay or pay.user_id != user.id:
            await query.answer(T.payment_check_failed(), show_alert=True)
            return
        if pay.status == PaymentStatus.succeeded:
            await query.answer("Платёж уже подтверждён.")
            return

        status = await payment_service.get_payment_status(yid)
        if status == "succeeded":
            text = await process_successful_order(
                session,
                bot,
                user,
                kind="trial" if pay.is_trial else "full",
                payment_external_id=yid,
                fetch_yookassa_method=True,
            )
            await crud.mark_payment_succeeded(session, pay.id)
            await session.commit()
            if query.message:
                await query.message.answer(text)
            await query.answer("Оплата подтверждена")
            return

        if status in ("canceled", "failed"):
            await crud.mark_payment_failed(session, pay.id)
            await session.commit()
            await query.answer(T.payment_check_failed(), show_alert=True)
            return

        await query.answer(T.payment_pending_check_later(), show_alert=True)
    except Exception as e:
        logger.exception("cb_check_payment")
        try:
            await session.rollback()
        except Exception:
            logger.exception("cb_check_payment rollback")
        if query.message:
            await query.message.answer(T.payment_invoice_error(_error_details(e)))
            await query.answer()
        else:
            await query.answer(T.error_generic(), show_alert=True)
