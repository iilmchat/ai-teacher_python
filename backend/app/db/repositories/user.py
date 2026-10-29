"""
User repository
"""
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.user import User, UserRole, UserLevel


class UserRepository(BaseRepository[User]):
    """Репозиторий для работы с пользователями"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """Получить пользователя по email"""
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def get_by_username(self, username: str) -> Optional[User]:
        """Получить пользователя по username"""
        result = await self.session.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()
    
    async def update_level(self, user_id: UUID, level: UserLevel) -> Optional[User]:
        """Обновить уровень пользователя"""
        return await self.update(user_id, level=level)
    
    async def update_role(self, user_id: UUID, role: UserRole) -> Optional[User]:
        """Обновить роль пользователя"""
        return await self.update(user_id, role=role)
