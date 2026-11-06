"""
User API endpoints (S5-002, S5-004).

Профиль и переключение уровня помощи. Профиль доступен всем авторизованным
пользователям; смена роли — только администратору (RBAC).
"""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user, require_role
from app.db.database import get_db
from app.db.repositories.user import UserRepository
from app.models.user import User, UserRole
from app.schemas.user import LevelUpdateRequest, UserResponse, UserSettingsUpdate
from app.services.levels import get_level_info, list_levels

router = APIRouter(prefix="/users", tags=["Users"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_active_user)]
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]


@router.get("/me", response_model=UserResponse)
async def get_profile(current_user: CurrentUser) -> User:
    """Профиль текущего пользователя"""
    return current_user


@router.patch("/me/level", response_model=UserResponse)
async def update_my_level(
    payload: LevelUpdateRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> User:
    """Переключить уровень помощи для новых сессий чата"""
    user_repo = UserRepository(db)
    updated = await user_repo.update_level(current_user.id, payload.level)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден"
        )
    return updated


@router.patch("/me/settings", response_model=UserResponse)
async def update_my_settings(
    payload: UserSettingsUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> User:
    """Обновить личные настройки пользователя (S43-004, S44-003).

    Настройки дополняются, а не заменяются: так клиент может менять одну
    настройку, не присылая весь объект.
    """
    user_repo = UserRepository(db)
    current = dict(current_user.settings or {})
    if "prompt_template" in payload.model_fields_set:
        if payload.prompt_template is None:
            current.pop("prompt_template", None)
        else:
            current["prompt_template"] = payload.prompt_template
    if "snippets" in payload.model_fields_set:
        if payload.snippets is None:
            current.pop("snippets", None)
        else:
            current["snippets"] = [
                snippet.model_dump() for snippet in payload.snippets
            ]
    updated = await user_repo.update(current_user.id, settings=current)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден"
        )
    return updated


@router.get("/me/level")
async def get_my_level(current_user: CurrentUser) -> dict[str, Any]:
    """Текущий уровень и его описание"""
    info = get_level_info(current_user.level)
    return {
        "level": info.level.value,
        "title": info.title,
        "description": info.description,
        "audience": info.audience,
        "gives_ready_code": info.gives_ready_code,
    }


@router.get("/levels")
async def get_levels() -> dict[str, Any]:
    """Все уровни ассистента с описаниями"""
    return {
        "levels": [
            {
                "level": info.level.value,
                "title": info.title,
                "description": info.description,
                "audience": info.audience,
                "gives_ready_code": info.gives_ready_code,
            }
            for info in list_levels()
        ]
    }


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: UUID, _: AdminUser, db: DbSession) -> User:
    """Карточка пользователя (только администратор)"""
    user = await UserRepository(db).get(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден"
        )
    return user


@router.patch("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: UUID,
    role: UserRole,
    _: AdminUser,
    db: DbSession,
) -> User:
    """Смена роли пользователя (только администратор)"""
    updated = await UserRepository(db).update_role(user_id, role)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден"
        )
    return updated


@router.post("/me/activity")
async def touch_activity(current_user: CurrentUser, db: DbSession) -> dict[str, str]:
    """Отметить активность пользователя (обновляет last_active)"""
    await UserRepository(db).update(current_user.id, last_active=datetime.utcnow())
    return {"status": "ok"}
