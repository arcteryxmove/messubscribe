# CRUD-операции (async)
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence, Tuple

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.database.models import Payment, PaymentStatus, Subscription, SubscriptionStatus, User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def get_user_by_telegram_id(
    session: AsyncSession,
    telegram_id: int,
) -> Optional[User]:
    r = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return r.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    username: Optional[str],
    full_name: str,
) -> User:
    u = User(telegram_id=telegram_id, username=username, full_name=full_name)
    session.add(u)
    await session.flush()
    return u


async def get_or_create_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    username: Optional[str],
    full_name: str,
) -> User:
    u = await get_user_by_telegram_id(session, telegram_id)
    if u:
        if username is not None:
            u.username = username
        if full_name:
            u.full_name = full_name
        return u
    return await create_user(
        session,
        telegram_id=telegram_id,
        username=username,
        full_name=full_name,
    )


async def wipe_user_subscription_data(session: AsyncSession, user_id: int) -> None:
    """Удаляет все подписки и платежи пользователя (для повторного теста сценария)."""
    await session.execute(delete(Payment).where(Payment.user_id == user_id))
    await session.execute(delete(Subscription).where(Subscription.user_id == user_id))
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(yookassa_payment_method_id=None),
    )


async def get_active_subscription(
    session: AsyncSession,
    user_id: int,
) -> Optional[Subscription]:
    """Активная подписка: оплаченный период или grace после неудачного списания."""
    now = _utcnow()
    r = await session.execute(
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            or_(
                Subscription.expires_at > now,
                and_(
                    Subscription.grace_until.isnot(None),
                    Subscription.grace_until > now,
                ),
            ),
            Subscription.status.in_(
                [
                    SubscriptionStatus.trial,
                    SubscriptionStatus.active,
                    SubscriptionStatus.cancelled,
                ],
            ),
        )
        .order_by(Subscription.expires_at.desc()),
    )
    return r.scalars().first()


async def count_subscriptions_by_status(
    session: AsyncSession,
    status: SubscriptionStatus,
) -> int:
    r = await session.execute(
        select(func.count()).select_from(Subscription).where(Subscription.status == status),
    )
    return int(r.scalar() or 0)


async def count_subscriptions_by_statuses(
    session: AsyncSession,
    statuses: Sequence[SubscriptionStatus],
) -> int:
    r = await session.execute(
        select(func.count()).select_from(Subscription).where(Subscription.status.in_(statuses)),
    )
    return int(r.scalar() or 0)


async def count_active_trials(session: AsyncSession) -> int:
    now = _utcnow()
    r = await session.execute(
        select(func.count()).select_from(Subscription).where(
            Subscription.status == SubscriptionStatus.trial,
            or_(
                Subscription.expires_at > now,
                and_(
                    Subscription.grace_until.isnot(None),
                    Subscription.grace_until > now,
                ),
            ),
        ),
    )
    return int(r.scalar() or 0)


async def count_active_like(session: AsyncSession) -> int:
    now = _utcnow()
    r = await session.execute(
        select(func.count()).select_from(Subscription).where(
            or_(
                Subscription.expires_at > now,
                and_(
                    Subscription.grace_until.isnot(None),
                    Subscription.grace_until > now,
                ),
            ),
            Subscription.status.in_(
                [
                    SubscriptionStatus.trial,
                    SubscriptionStatus.active,
                    SubscriptionStatus.cancelled,
                ],
            ),
        ),
    )
    return int(r.scalar() or 0)


async def sum_payments_kopecks(
    session: AsyncSession,
    *,
    since: datetime,
) -> int:
    r = await session.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.status == PaymentStatus.succeeded,
            Payment.paid_at.isnot(None),
            Payment.paid_at >= since,
        ),
    )
    return int(r.scalar() or 0)


async def search_users(
    session: AsyncSession,
    *,
    q: str,
    limit: int = 20,
) -> Sequence[User]:
    q = q.strip()
    if not q:
        return []
    if q.isdigit():
        tid = int(q)
        r = await session.execute(
            select(User).where(User.telegram_id == tid).limit(limit),
        )
        return r.scalars().all()
    r = await session.execute(
        select(User)
        .where(User.username.ilike(f"%{q}%"))
        .limit(limit),
    )
    return r.scalars().all()


async def set_user_banned(
    session: AsyncSession,
    user_id: int,
    banned: bool,
) -> None:
    await session.execute(update(User).where(User.id == user_id).values(is_banned=banned))


async def list_telegram_ids_active_subscribers(session: AsyncSession) -> list[int]:
    now = _utcnow()
    r = await session.execute(
        select(User.telegram_id)
        .join(Subscription, Subscription.user_id == User.id)
        .where(
            or_(
                Subscription.expires_at > now,
                and_(
                    Subscription.grace_until.isnot(None),
                    Subscription.grace_until > now,
                ),
            ),
            Subscription.status.in_(
                [
                    SubscriptionStatus.trial,
                    SubscriptionStatus.active,
                    SubscriptionStatus.cancelled,
                ],
            ),
            User.is_banned.is_(False),
        ),
    )
    return [int(x[0]) for x in r.all()]


async def update_user_payment_method(
    session: AsyncSession,
    user_id: int,
    payment_method_id: Optional[str],
) -> None:
    await session.execute(
        update(User).where(User.id == user_id).values(
            yookassa_payment_method_id=payment_method_id,
        ),
    )


# --- Подписки и платежи ---


async def create_pending_payment(
    session: AsyncSession,
    *,
    user_id: int,
    subscription_id: Optional[int],
    amount: int,
    yookassa_payment_id: str,
    is_trial: bool,
) -> Payment:
    p = Payment(
        user_id=user_id,
        subscription_id=subscription_id,
        amount=amount,
        status=PaymentStatus.pending,
        yookassa_payment_id=yookassa_payment_id,
        is_trial=is_trial,
    )
    session.add(p)
    await session.flush()
    return p


async def create_payment_succeeded(
    session: AsyncSession,
    *,
    user_id: int,
    subscription_id: Optional[int],
    amount: int,
    yookassa_payment_id: str,
    is_trial: bool,
    paid_at: Optional[datetime] = None,
) -> Payment:
    """Запись успешного платежа (Telegram Payments — сразу succeeded)."""
    p = Payment(
        user_id=user_id,
        subscription_id=subscription_id,
        amount=amount,
        status=PaymentStatus.succeeded,
        yookassa_payment_id=yookassa_payment_id,
        is_trial=is_trial,
        paid_at=paid_at or _utcnow(),
    )
    session.add(p)
    await session.flush()
    return p


async def mark_payment_succeeded(
    session: AsyncSession,
    payment_id: int,
    paid_at: Optional[datetime] = None,
) -> None:
    await session.execute(
        update(Payment)
        .where(Payment.id == payment_id)
        .values(
            status=PaymentStatus.succeeded,
            paid_at=paid_at or _utcnow(),
        ),
    )


async def mark_payment_failed(session: AsyncSession, payment_id: int) -> None:
    await session.execute(
        update(Payment).where(Payment.id == payment_id).values(status=PaymentStatus.failed),
    )


async def create_trial_subscription(
    session: AsyncSession,
    *,
    user_id: int,
    days: int,
) -> Subscription:
    now = _utcnow()
    exp = now + timedelta(days=days)
    sub = Subscription(
        user_id=user_id,
        status=SubscriptionStatus.trial,
        trial_used=True,
        started_at=now,
        expires_at=exp,
        next_charge_at=exp,
        auto_renew=True,
    )
    session.add(sub)
    await session.flush()
    return sub


async def activate_or_extend_subscription(
    session: AsyncSession,
    *,
    user_id: int,
    period_days: int,
) -> Subscription:
    """Создаёт или продлевает основную подписку (в т.ч. перевод с trial на active)."""
    now = _utcnow()
    exp = now + timedelta(days=period_days)
    sub = await get_active_subscription(session, user_id)
    if sub:
        if sub.status == SubscriptionStatus.trial:
            sub.status = SubscriptionStatus.active
            sub.started_at = now
        else:
            sub.status = SubscriptionStatus.active
        sub.expires_at = exp
        sub.next_charge_at = exp
        sub.auto_renew = True
        sub.grace_until = None
        sub.reminder_24h_sent_at = None
        await session.flush()
        return sub

    r = await session.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.id.desc()),
    )
    last = r.scalars().first()
    trial_flag = last.trial_used if last else False

    new_sub = Subscription(
        user_id=user_id,
        status=SubscriptionStatus.active,
        trial_used=trial_flag,
        started_at=now,
        expires_at=exp,
        next_charge_at=exp,
        auto_renew=True,
    )
    session.add(new_sub)
    await session.flush()
    return new_sub


async def extend_subscription_after_charge(
    session: AsyncSession,
    sub: Subscription,
    period_days: int,
) -> None:
    now = _utcnow()
    base = sub.expires_at if sub.expires_at > now else now
    new_exp = base + timedelta(days=period_days)
    sub.expires_at = new_exp
    sub.next_charge_at = new_exp
    sub.status = SubscriptionStatus.active
    sub.grace_until = None
    sub.reminder_24h_sent_at = None


async def cancel_subscription_user(
    session: AsyncSession,
    sub: Subscription,
) -> None:
    """Отмена автопродления: статус cancelled, доступ до expires_at."""
    sub.auto_renew = False
    sub.status = SubscriptionStatus.cancelled


async def expire_subscription(
    session: AsyncSession,
    sub: Subscription,
) -> None:
    sub.status = SubscriptionStatus.expired
    sub.next_charge_at = None
    sub.auto_renew = False


async def set_grace_period(
    session: AsyncSession,
    sub: Subscription,
    until: datetime,
) -> None:
    sub.grace_until = until


async def set_reminder_sent(
    session: AsyncSession,
    sub: Subscription,
) -> None:
    sub.reminder_24h_sent_at = _utcnow()


async def subscriptions_due_for_reminder(
    session: AsyncSession,
    within_hours: int = 24,
) -> Sequence[Subscription]:
    """Подписки, у которых за 24ч до expires_at ещё не отправляли напоминание."""
    now = _utcnow()
    window_end = now + timedelta(hours=within_hours)
    r = await session.execute(
        select(Subscription)
        .options(selectinload(Subscription.user))
        .where(
            Subscription.expires_at > now,
            Subscription.expires_at <= window_end,
            Subscription.reminder_24h_sent_at.is_(None),
            Subscription.status.in_(
                [SubscriptionStatus.trial, SubscriptionStatus.active],
            ),
            Subscription.auto_renew.is_(True),
        ),
    )
    return r.scalars().all()


async def subscriptions_need_recurring_charge(
    session: AsyncSession,
) -> Sequence[Subscription]:
    """Срок истёк — автосписание (не в grace-окне, автопродление включено)."""
    now = _utcnow()
    r = await session.execute(
        select(Subscription)
        .options(selectinload(Subscription.user))
        .where(
            Subscription.expires_at <= now,
            Subscription.auto_renew.is_(True),
            Subscription.status.in_(
                [
                    SubscriptionStatus.trial,
                    SubscriptionStatus.active,
                ],
            ),
            Subscription.grace_until.is_(None),
        ),
    )
    return r.scalars().all()


async def subscriptions_past_grace(
    session: AsyncSession,
) -> Sequence[Subscription]:
    """Grace истёк, подписка не продлена — кик и expired."""
    now = _utcnow()
    r = await session.execute(
        select(Subscription)
        .options(selectinload(Subscription.user))
        .where(
            Subscription.grace_until.isnot(None),
            Subscription.grace_until <= now,
            Subscription.expires_at <= now,
            Subscription.status.in_(
                [SubscriptionStatus.trial, SubscriptionStatus.active],
            ),
        ),
    )
    return r.scalars().all()


async def cancelled_subscriptions_to_close(
    session: AsyncSession,
) -> Sequence[Subscription]:
    """Cancelled без автопродления — закрыть по expires_at."""
    now = _utcnow()
    r = await session.execute(
        select(Subscription)
        .options(selectinload(Subscription.user))
        .where(
            Subscription.status == SubscriptionStatus.cancelled,
            Subscription.expires_at <= now,
        ),
    )
    return r.scalars().all()


async def has_used_trial_offer(session: AsyncSession, user_id: int) -> bool:
    """Пробный период уже был оформлен на этот аккаунт."""
    r = await session.execute(
        select(func.count()).select_from(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.trial_used.is_(True),
        ),
    )
    return int(r.scalar() or 0) > 0


async def get_user_with_subscription(
    session: AsyncSession,
    telegram_id: int,
) -> Tuple[User, Optional[Subscription]]:
    r = await session.execute(
        select(User)
        .options(selectinload(User.subscriptions))
        .where(User.telegram_id == telegram_id),
    )
    user = r.scalar_one_or_none()
    if not user:
        raise ValueError("user not found")
    sub = await get_active_subscription(session, user.id)
    return user, sub
