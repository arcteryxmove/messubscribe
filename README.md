# messubscribe — Telegram-бот подписки на закрытый канал

Production-ready бот на **Python 3.11+**, **aiogram 3.x**, **PostgreSQL + SQLAlchemy (async)**, **Alembic**, **ЮKassa** (Telegram Payments API), **APScheduler** (проверка подписок каждые 30 минут), **Docker**.

## Возможности

- Пробный период **1 ₽ / 3 дня** (один раз на аккаунт).
- Основная подписка **299 ₽ / 3 дня** с автопродлением через **ЮKassa** (при сохранённом `payment_method_id` после первой оплаты).
- Напоминание за 24 часа до окончания периода, при неудачном списании — уведомление и **24 часа** на оплату вручную, затем исключение из канала.
- Кабинет `/cabinet`, отмена автопродления с сохранением доступа до конца оплаченного периода.
- Админ-панель `/admin` (только `ADMIN_IDS`): статистика, поиск пользователя, бан/разбан, рассылка активным подписчикам.

## Требования

- Docker и Docker Compose **или** локально: Python 3.11+, PostgreSQL 15+.
- В [BotFather](https://t.me/BotFather) подключён провайдер платежей **ЮKassa** (получите `PAYMENTS_TOKEN`).
- Бот добавлен в закрытый канал как **администратор** с правом «добавлять пользователей» / приглашения.
- В личном кабинете ЮKassa включено сохранение способа оплаты для рекуррентных платежей (при необходимости).

## Быстрый старт (Docker)

1. Скопируйте `.env.example` в `.env` и заполните:

   - `BOT_TOKEN` — токен бота.
   - `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY` — из личного кабинета ЮKassa.
   - `CHANNEL_ID` — id закрытого канала (отрицательное число, например `-100...`).
   - `ADMIN_IDS` — список telegram id администраторов через запятую.
   - `PAYMENTS_TOKEN` — токен провайдера платежей из BotFather.

2. Сборка и запуск:

```bash
docker compose build
docker compose up -d
```

Логи приложения пишутся в том `bot_logs` в `logs/bot.log` внутри контейнера.

`DATABASE_URL` в `docker-compose.yml` задаётся для сервиса `db` автоматически; при локальном запуске без Docker укажите свой URL в `.env`.

## Локальный запуск без Docker

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export $(grep -v '^#' .env | xargs)  # или используйте direnv
alembic upgrade head
python -m bot.main
```

Убедитесь, что `DATABASE_URL` указывает на доступный PostgreSQL.

## Deploy на Railway

Для Railway задайте переменные окружения в сервисе:

- `BOT_TOKEN`
- `DATABASE_URL` (Railway Postgres URL)
- `CHANNEL_ID` (отрицательный id канала)
- `PAYMENTS_TOKEN` (токен платежей Telegram от BotFather)
- `YOOKASSA_SHOP_ID`
- `YOOKASSA_SECRET_KEY`
- `ADMIN_IDS`
- `SUPPORT_USERNAME=@melon_edu`
- `MOCK_PAYMENTS=false`

Стартовая команда:

```bash
python -m bot.main
```

## Структура

- `bot/main.py` — точка входа, middleware, планировщик, graceful shutdown (dispose engine, остановка scheduler).
- `bot/config.py` — настройки (pydantic-settings).
- `bot/database/` — модели, движок, CRUD.
- `bot/handlers/` — хендлеры.
- `bot/services/` — ЮKassa, доступ к каналу, планировщик.
- `bot/texts/messages.py` — тексты.
- `bot/migrations/` — Alembic.

## Примечания по бизнес-логике

- Автосписание выполняется через API ЮKassa по сохранённому `payment_method_id`. После оплаты через Telegram Payments бот запрашивает платёж в ЮKassa и пытается сохранить метод. Если метод недоступен, при продлении пользователь получит уведомление и сможет оплатить вручную по счёту из бота.
- Для пользователей в **grace-периоде** (после неудачного списания) подписка по-прежнему считается активной для кабинета и рассылки до истечения `grace_until`.

## Команды

| Команда | Описание |
|--------|----------|
| `/start` | Приветствие и оплата |
| `/cabinet` | Мой кабинет |
| `/admin` | Админ-панель (только из `ADMIN_IDS`) |
| `/cancel` | Сброс сценария админа (поиск/рассылка) |

## Лицензия

Проект создан для внутреннего использования; при необходимости добавьте свою лицензию.
