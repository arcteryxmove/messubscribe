# Асинхронный движок SQLAlchemy и фабрика сессий
from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from bot.config import get_settings
from bot.database.models import Base  # модели подтягиваются из models.py


def _create_engine():
    settings = get_settings()
    url = settings.database_url
    if url.startswith("sqlite"):
        try:
            u = make_url(url)
            if u.database:
                Path(u.database).parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            Path("data").mkdir(parents=True, exist_ok=True)
        return create_async_engine(
            url,
            echo=False,
            poolclass=NullPool,
            connect_args={"check_same_thread": False},
        )
    return create_async_engine(
        url,
        echo=False,
        pool_pre_ping=True,
    )


engine = _create_engine()

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    """Создание таблиц (SQLite — без Alembic; в prod часто используют Alembic)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
