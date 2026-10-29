"""
Dependency Injection контейнер
"""
from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Получение сессии базы данных
    
    Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    from app.db.database import async_session_factory
    
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_settings():
    """Получение настроек приложения"""
    return settings
