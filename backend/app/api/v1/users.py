"""
User API endpoints (S5-002, S5-004).

Профиль и переключение уровня помощи. Профиль доступен всем авторизованным
пользователям; смена роли — только администратору (RBAC).
"""

import json
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.security import (
    get_current_active_user,
    hash_password,
    issue_token_pair,
    require_role,
    verify_password,
)
from app.db.database import get_db
from app.db.repositories.user import UserRepository
from app.models.user import User, UserRole
from app.schemas.user import (
    LevelUpdateRequest,
    PasswordChangeRequest,
    UserResponse,
    UserSettingsUpdate,
)
from app.models.user import User, UserRole, UserSession
from app.services.audit_service import record_audit
from app.services.levels import get_level_info, list_levels
from app.services.personal_export import collect_user_data, export_filename
from app.services.sessions import (
    current_jti,
    list_sessions,
    revoke_all_sessions,
    revoke_session,
    start_session,
)

router = APIRouter(prefix="/users", tags=["Users"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_active_user)]
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]


@router.get("/me", response_model=UserResponse)
async def get_profile(current_user: CurrentUser) -> User:
    """Профиль текущего пользователя"""
    return current_user


@router.post("/me/password")
async def change_password(
    payload: PasswordChangeRequest,
    current_user: CurrentUser,
    db: DbSession,
    request: Request,
) -> dict[str, str]:
    """Сменить пароль и отозвать чужие refresh-токены (S45-001).

    Проверка текущего пароля обязательна, чтобы токен с чужого устройства
    не менял пароль. Смена увеличивает `token_version`: refresh-токены,
    выданные раньше, при обновлении получают 401. Текущая сессия не
    страдает — новая пара возвращается в ответе (KI-028).
    """
    if not await run_in_threadpool(
        verify_password, payload.current_password, current_user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный текущий пароль",
        )

    user_repo = UserRepository(db)
    # bcrypt синхронный (~0.1–0.3 с): в потоке, как в register/login.
    new_hash = await run_in_threadpool(hash_password, payload.new_password)
    updated = await user_repo.update(
        current_user.id,
        hashed_password=new_hash,
        token_version=current_user.token_version + 1,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден"
        )

    await record_audit(
        db,
        actor=current_user,
        action="user.password_changed",
        entity_type="user",
        entity_id=current_user.id,
        request=request,
    )

    # Текущее устройство получает пару с новой версией и остаётся в сессии.
    # Все строки сессий отзываются, для этого устройства создаётся новая
    # (S45-005): список «Активные сессии» не показывает старые устройства.
    await revoke_all_sessions(db, current_user.id)
    jti = await start_session(db, updated, request)
    return {**issue_token_pair(updated, jti=jti), "token_type": "bearer"}


@router.get("/me/export")
async def export_my_data(
    current_user: CurrentUser,
    db: DbSession,
    request: Request,
) -> Response:
    """Выгрузить все свои данные одним JSON-файлом (S45-003).

    Профиль, прогресс по задачам и попытки, сессии чата с сообщениями
    (без служебных эмбеддингов), уведомления и достижения. Выгружаются
    только данные запрашивающего: чужого профиля/чужих чатов там нет.
    Файл отдаётся с `Content-Disposition: attachment`. Действие
    фиксируется в журнале аудита (`user.data_exported`).
    """
    data = await collect_user_data(db, current_user)
    await record_audit(
        db,
        actor=current_user,
        action="user.data_exported",
        entity_type="user",
        entity_id=current_user.id,
        request=request,
    )
    payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{export_filename()}"'},
    )


def _session_dict(session: UserSession, *, current: bool) -> dict[str, Any]:
    """Представление сессии для UI (PRIVACY.md: UA/IP только владельцу)"""
    return {
        "id": str(session.id),
        "created_at": session.created_at.isoformat(),
        "last_used_at": session.last_used_at.isoformat(),
        "user_agent": session.user_agent,
        "ip": session.ip,
        "current": current,
    }


@router.get("/me/sessions")
async def get_my_sessions(
    current_user: CurrentUser,
    db: DbSession,
    request: Request,
) -> list[dict[str, Any]]:
    """Список активных сессий пользователя (S45-005)"""
    jti = current_jti(request)
    sessions = await list_sessions(db, current_user.id)
    return [
        _session_dict(session, current=bool(jti and session.jti == jti))
        for session in sessions
    ]


@router.delete("/me/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_my_session(
    session_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    request: Request,
) -> None:
    """Отозвать сессию (refresh-токен) другого устройства (S45-005).

    Текущую сессию так не отозвать: для этого есть выход из аккаунта,
    иначе клиент остался бы без пары токенов. Чужая сессия — 404.
    """
    target = await db.get(UserSession, session_id)
    if (
        target is None
        or target.user_id != current_user.id
        or target.revoked_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Сессия не найдена"
        )
    jti = current_jti(request)
    if jti and target.jti == jti:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя отозвать текущую сессию — выйдите из аккаунта",
        )
    session = await revoke_session(db, current_user.id, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Сессия не найдена"
        )
    await record_audit(
        db,
        actor=current_user,
        action="user.session_revoked",
        entity_type="user_session",
        entity_id=session_id,
        request=request,
    )


@router.post("/me/sessions/revoke-others")
async def revoke_other_sessions(
    current_user: CurrentUser,
    db: DbSession,
    request: Request,
) -> dict[str, Any]:
    """«Выйти на всех устройствах» (S45-005, KI-028).

    Увеличивает `token_version` (все refresh-токены, включая текущий,
    перестают работать), отзывает строки сессий и выдаёт текущему
    устройству новую пару — оно остаётся в системе.
    """
    user_repo = UserRepository(db)
    updated = await user_repo.update(
        current_user.id, token_version=current_user.token_version + 1
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден"
        )
    revoked = await revoke_all_sessions(db, current_user.id)
    jti = await start_session(db, updated, request)
    await record_audit(
        db,
        actor=current_user,
        action="user.sessions_revoked",
        entity_type="user",
        entity_id=current_user.id,
        payload={"revoked": revoked},
        request=request,
    )
    return {
        **issue_token_pair(updated, jti=jti),
        "token_type": "bearer",
        "revoked": revoked,
    }


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
    # S45-004: язык интерфейса и настройки уведомлений. `None` возвращает
    # ключ к значению по умолчанию (см. notification_preferences).
    for key in (
        "language",
        "email_notifications",
        "deadline_notifications",
        "deadline_days",
    ):
        if key in payload.model_fields_set:
            value = getattr(payload, key)
            if value is None:
                current.pop(key, None)
            else:
                current[key] = value
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
