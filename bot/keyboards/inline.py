# Inline-клавиатуры
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.texts import messages as T


def kb_start_main(*, has_active: bool, trial_available: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if has_active:
        rows.append(
            [InlineKeyboardButton(text=T.btn_cabinet(), callback_data="cabinet")],
        )
        return InlineKeyboardMarkup(inline_keyboard=rows)

    if trial_available:
        rows.append(
            [
                InlineKeyboardButton(
                    text=T.btn_trial(),
                    callback_data="pay_trial",
                ),
            ],
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=T.btn_subscribe(),
                callback_data="pay_full",
            ),
        ],
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_cabinet() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=T.btn_cancel_sub(),
                    callback_data="cancel_sub_confirm",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=T.btn_support(),
                    callback_data="support",
                ),
            ],
        ],
    )


def kb_cancel_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=T.btn_confirm_cancel(),
                    callback_data="cancel_sub_yes",
                ),
                InlineKeyboardButton(
                    text=T.btn_keep_sub(),
                    callback_data="cancel_sub_no",
                ),
            ],
        ],
    )


def kb_renew_manual() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=T.btn_renew_manual(),
                    callback_data="pay_full",
                ),
            ],
        ],
    )


def kb_pay_manual() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=T.btn_pay_manual(),
                    callback_data="pay_full",
                ),
            ],
        ],
    )


def kb_yookassa_checkout(url: str, payment_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Оплатить в ЮKassa", url=url)],
            [InlineKeyboardButton(text="Проверить оплату", callback_data=f"check_pay:{payment_id}")],
        ],
    )


def kb_admin() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Статистика",
                    callback_data="admin_stats",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Поиск пользователя",
                    callback_data="admin_search",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Рассылка",
                    callback_data="admin_broadcast",
                ),
            ],
        ],
    )


def kb_admin_user_actions(telegram_id: int, banned: bool) -> InlineKeyboardMarkup:
    ban_cd = f"admin_unban:{telegram_id}" if banned else f"admin_ban:{telegram_id}"
    ban_text = "Снять бан" if banned else "Забанить"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=ban_text, callback_data=ban_cd),
            ],
        ],
    )
