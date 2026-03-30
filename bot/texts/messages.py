# Тексты бота (RU)
from __future__ import annotations

from datetime import datetime
from typing import Optional


def welcome_title() -> str:
    return "Инструменты роста для предпринимателей"


def welcome_body() -> str:
    return (
        "Закрытый канал с чек-листами для саморазвития: практика без воды, "
        "которую можно внедрять в бизнес уже сегодня.\n\n"
        "• <b>Готовые чек-листы</b> — структура вместо хаоса в задачах и проектах.\n"
        "• <b>Экономия времени</b> — фокус на действиях с максимальным эффектом.\n"
        "• <b>Практика без воды</b> — только инструменты для роста, команды и финансов.\n"
        "• <b>Сообщество</b> — единый контекст: предприниматели и владельцы бизнеса.\n\n"
        "Начните с пробного доступа за символический рубль — оцените формат и пользу."
    )


def welcome_has_subscription() -> str:
    return (
        "У вас уже есть активный доступ к каналу. "
        "Откройте «Мой кабинет», чтобы посмотреть статус и даты."
    )


def welcome_reset_hint() -> str:
    return "\n\n<i>Повторить сценарий с нуля: отправьте /reset</i>"


def reset_done() -> str:
    return (
        "Готово: история подписок и платежей в боте для этого аккаунта очищена. "
        "Нажмите /start — снова будет полный путь до оплаты."
    )


def reset_denied() -> str:
    return (
        "Команда доступна только в режиме без настоящих платежей "
        "(MOCK_PAYMENTS и без PAYMENTS_TOKEN)."
    )


def btn_trial() -> str:
    return "Попробовать за 1 ₽"


def btn_subscribe() -> str:
    return "Подписаться за 299 ₽ / 3 дня"


def btn_cabinet() -> str:
    return "Мой кабинет"


def btn_support() -> str:
    return "Связаться с поддержкой"


def btn_cancel_sub() -> str:
    return "Отменить подписку"


def btn_confirm_cancel() -> str:
    return "Да, отменить автопродление"


def btn_keep_sub() -> str:
    return "Оставить подписку"


def btn_renew_manual() -> str:
    return "Продлить вручную"


def btn_pay_manual() -> str:
    return "Оплатить вручную"


def payments_not_configured() -> str:
    return (
        "Оплата в боте пока не подключена (нет PAYMENTS_TOKEN в настройках). "
        "Напишите администратору или попробуйте позже."
    )


def yookassa_checkout_prompt() -> str:
    return (
        "Нажмите кнопку ниже, чтобы перейти на страницу оплаты ЮKassa.\n"
        "После оплаты вернитесь в бот и нажмите «Проверить оплату»."
    )


def payment_pending_check_later() -> str:
    return "Платёж ещё не подтверждён. Оплатите по ссылке и нажмите «Проверить оплату» снова."


def payment_check_failed() -> str:
    return "Не удалось проверить платёж. Попробуйте ещё раз через несколько секунд."


def payment_invoice_error(details: Optional[str] = None) -> str:
    base = (
        "Не удалось открыть форму оплаты в Telegram. "
        "Проверьте PAYMENTS_TOKEN в Railway (из BotFather -> Payments) "
        "и что для бота подключен провайдер ЮKassa."
    )
    if details:
        return f"{base}\n\nТех.детали: <code>{details[:180]}</code>"
    return base


def trial_used_only_full() -> str:
    return (
        "Пробный период на ваш аккаунт уже использован — "
        "доступна только полная подписка."
    )


def invoice_title_trial() -> str:
    return "Пробный доступ на 3 дня"


def invoice_description_trial() -> str:
    return "Закрытый канал: чек-листы для предпринимателей (пробный период)"


def invoice_title_full() -> str:
    return "Подписка на 3 дня"


def invoice_description_full() -> str:
    return "Доступ к закрытому каналу с чек-листами (3 дня)"


def payment_success_trial_already_in_channel() -> str:
    return (
        "Оплата прошла успешно — включён <b>пробный период на 3 дня</b>.\n\n"
        "Вы уже состоите в канале — приятного использования."
    )


def payment_success_trial(invite_link: str) -> str:
    return (
        "Оплата прошла успешно — включён <b>пробный период на 3 дня</b>.\n\n"
        f"Ваша персональная ссылка на канал (одно использование):\n{invite_link}\n\n"
        "Сохраните её: после входа вы получите доступ к материалам. "
        "По окончании пробного периода подключится основной тариф с автопродлением."
    )


def payment_success_full(invite_link: Optional[str]) -> str:
    base = (
        "Оплата прошла успешно — подписка активна на <b>3 дня</b> с автопродлением."
    )
    if invite_link:
        return (
            base
            + f"\n\nСсылка для входа в канал:\n{invite_link}\n\n"
            "Если вы уже в канале, просто продолжайте пользоваться доступом."
        )
    return base + "\n\nВы уже состоите в канале — приятного использования."


def pre_checkout_error() -> str:
    return "Не удалось подтвердить платёж. Попробуйте ещё раз или напишите в поддержку."


def cabinet_no_subscription() -> str:
    return "Активной подписки нет. Откройте /start, чтобы оформить доступ."


def cabinet_header() -> str:
    return "Мой кабинет"


def cabinet_status(
    status_label: str,
    expires: Optional[datetime],
    next_charge: Optional[datetime],
) -> str:
    exp_s = expires.strftime("%d.%m.%Y %H:%M UTC") if expires else "—"
    nc = next_charge.strftime("%d.%m.%Y %H:%M UTC") if next_charge else "—"
    return (
        f"Статус: <b>{status_label}</b>\n"
        f"Действует до: <b>{exp_s}</b>\n"
        f"Следующее списание: <b>{nc}</b>"
    )


def cancel_confirm() -> str:
    return (
        "Отменить автопродление? Доступ сохранится до конца оплаченного периода, "
        "после даты окончания доступ к каналу будет закрыт."
    )


def cancel_done() -> str:
    return (
        "Автопродление отключено. Вы пользуетесь каналом до конца текущего периода. "
        "Спасибо, что были с нами."
    )


def reminder_24h() -> str:
    return (
        "Через 24 часа истекает оплаченный период подписки. "
        "Мы попробуем продлить доступ автоматически. "
        "Если хотите продлить вручную — нажмите кнопку ниже."
    )


def charge_failed() -> str:
    return (
        "Не удалось списать оплату за продление. "
        "У вас есть 24 часа, чтобы оплатить вручную — иначе доступ к каналу будет закрыт."
    )


def auto_renew_success() -> str:
    return "Автопродление прошло успешно — подписка продлена на 3 дня."


def kicked_expired() -> str:
    return (
        "Срок оплаты истёк — доступ к закрытому каналу отключён. "
        "Чтобы вернуться, оформите подписку снова через /start."
    )


def admin_denied() -> str:
    return "Недостаточно прав."


def admin_menu() -> str:
    return "Админ-панель: выберите действие."


def admin_stats(
    active: int,
    trial: int,
    expired: int,
    revenue_today: int,
    revenue_7: int,
    revenue_30: int,
) -> str:
    return (
        "<b>Статистика</b>\n"
        f"Активных доступов (по дате): {active}\n"
        f"Пробных (статус trial): {trial}\n"
        f"Истёкших записей: {expired}\n\n"
        f"Выручка (успешные платежи):\n"
        f"• сегодня: {revenue_today / 100:.2f} ₽\n"
        f"• 7 дней: {revenue_7 / 100:.2f} ₽\n"
        f"• 30 дней: {revenue_30 / 100:.2f} ₽"
    )


def admin_search_prompt() -> str:
    return "Введите telegram_id (число) или часть @username:"


def admin_user_card(
    tid: int,
    username: Optional[str],
    name: str,
    banned: bool,
) -> str:
    u = f"@{username}" if username else "—"
    b = "да" if banned else "нет"
    return (
        f"<b>Пользователь</b>\n"
        f"telegram_id: <code>{tid}</code>\n"
        f"username: {u}\n"
        f"имя: {name}\n"
        f"бан: {b}"
    )


def admin_broadcast_prompt() -> str:
    return "Отправьте сообщение для рассылки активным подписчикам (текст или пост):"


def admin_broadcast_done(sent: int, failed: int) -> str:
    return f"Рассылка завершена: доставлено ~{sent}, ошибок ~{failed}."


def admin_search_empty() -> str:
    return "Никого не найдено."


def admin_fsm_reset() -> str:
    return "Состояние админ-формы сброшено."


def admin_user_not_found() -> str:
    return "Пользователь не найден."


def subscription_ended_no_renew() -> str:
    return (
        "Период подписки завершён — доступ к каналу закрыт. "
        "Вернитесь через /start."
    )


def admin_ban_ok() -> str:
    return "Пользователь заблокирован."


def admin_unban_ok() -> str:
    return "Блокировка снята."


def support_message(username: Optional[str]) -> str:
    if username:
        return f"Напишите в поддержку: @{username.lstrip('@')}"
    return "Контакт поддержки не настроен (SUPPORT_USERNAME в .env)."


def error_generic() -> str:
    return "Произошла ошибка. Мы уже разбираемся. Попробуйте позже."


def banned_message() -> str:
    return "Доступ для вашего аккаунта ограничен."
