"""
Authentication API endpoints
"""
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

logger = structlog.get_logger(__name__)

from app.core.security import (
    decode_token,
    get_current_active_user,
    get_current_user,
    hash_password,
    issue_token_pair,
    token_version_from_payload,
    verify_password,
)
from app.db.database import get_db
from app.db.repositories.user import UserRepository
from app.models.user import User, UserLevel, UserRole
from app.schemas.user import DeleteAccountRequest, UserCreate, UserResponse, UserUpdate
from app.services.audit_service import record_audit
from app.services.sessions import rotate_session, start_session

router = APIRouter(prefix="/auth", tags=["Authentication"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: DbSession) -> User:
    """Регистрация нового пользователя"""
    user_repo = UserRepository(db)

    if await user_repo.get_by_email(user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    if await user_repo.get_by_username(user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )

    # Роль и уровень при регистрации не принимаются от клиента:
    # иначе любой мог бы зарегистрироваться преподавателем/админом.
    # Повышение роли — только через PATCH /users/{id}/role (админ).
    user = User(
        email=user_data.email,
        username=user_data.username,
        # bcrypt синхронный и занимает ~0.1–0.3 с: в потоке, чтобы не
        # блокировать event loop на время регистрации (аудит v0.3.3).
        hashed_password=await run_in_threadpool(hash_password, user_data.password),
        role=UserRole.STUDENT,
        level=UserLevel.BASIC,
    )
    return await user_repo.create(user)


@router.post("/login")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
    request: Request,
) -> dict[str, Any]:
    """Вход по username или email; возвращает пару токенов"""
    user_repo = UserRepository(db)

    user = await user_repo.get_by_username(form_data.username)
    if not user:
        user = await user_repo.get_by_email(form_data.username)

    # bcrypt — в потоке (не блокирует event loop), сравнение — до проверки
    # is_active, чтобы ответ не зависел от существования аккаунта.
    password_ok = (
        await run_in_threadpool(
            verify_password, form_data.password, user.hashed_password
        )
        if user is not None
        else False
    )
    if user is None or not password_ok or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    await user_repo.update(user.id, last_active=datetime.utcnow())

    # Сессия (устройство) с `jti`: её видно в списке и можно отозвать (S45-005).
    jti = await start_session(db, user, request)

    # `tv` в payload: смена пароля увеличивает версию и обнуляет все
    # выданные раньше refresh-токены (S45-001).
    return {
        **issue_token_pair(user, jti=jti),
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "role": user.role.value,
            "level": user.level.value,
        },
    }


def _user_id_from_payload(payload: dict[str, Any] | None) -> UUID:
    """Извлекает UUID пользователя из payload токена"""
    invalid_token = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not payload or payload.get("type") != "refresh":
        raise invalid_token

    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise invalid_token

    try:
        return UUID(subject)
    except ValueError:
        raise invalid_token from None


@router.post("/refresh")
async def refresh_tokens(refresh_token: str, db: DbSession) -> dict[str, str]:
    """Обновление пары токенов по refresh token"""
    payload = decode_token(refresh_token)
    user_id = _user_id_from_payload(payload)
    user = await UserRepository(db).get(user_id)

    # Удалённый/заблокированный аккаунт не должен обновлять токены: иначе
    # refresh пережил бы DELETE /auth/me (аудит v0.3.3).
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Токены, выданные до смены пароля, отклоняются даже при верном
    # payload (S45-001): версия в токене ниже текущей.
    if token_version_from_payload(payload) != user.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Сессия: отозванная/несуществующая строка → 401, иначе `jti`
    # ротируется, чтобы старый refresh-токен больше не работал (S45-005).
    raw_jti = (payload or {}).get("jti")
    new_jti = await rotate_session(db, user, str(raw_jti) if raw_jti else None)

    return {
        **issue_token_pair(user, jti=new_jti),
        "token_type": "bearer",
    }


@router.post("/logout")
async def logout(
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    """Выход: клиент должен удалить токены у себя"""
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """Информация о текущем пользователе"""
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    update_data: UserUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: DbSession,
) -> User:
    """Обновление профиля текущего пользователя"""
    user_repo = UserRepository(db)
    update_dict: dict[str, Any] = update_data.model_dump(exclude_unset=True)

    new_email = update_dict.get("email")
    if new_email is not None and new_email != current_user.email:
        if await user_repo.get_by_email(new_email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

    new_username = update_dict.get("username")
    if new_username is not None and new_username != current_user.username:
        if await user_repo.get_by_username(new_username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
            )

    old_email = current_user.email
    updated_user = await user_repo.update(current_user.id, **update_dict)
    if updated_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Смена e-mail: письмо на старый адрес (best-effort, S45-002) — у
    # владельца останется способ заметить чужой доступ к аккаунту.
    if new_email is not None and new_email != old_email:
        await _notify_email_change(old_email, new_email)

    return updated_user


async def _notify_email_change(old_email: str, new_email: str) -> None:
    """Отправить уведомление о смене e-mail, не ломая PATCH (S45-002)"""
    from app.services.email import get_email_sender, send_email_change_email

    try:
        await send_email_change_email(
            get_email_sender(), to=old_email, new_email=new_email
        )
    except Exception as exc:  # noqa: BLE001 — уведомление не должно ломать API
        logger.warning("email_change_notice_failed", error=str(exc))


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    payload: DeleteAccountRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: DbSession,
    request: Request,
) -> Response:
    """Удалить свой аккаунт (S26-004): анонимизация и блокировка входа.

    Необратимо: username/email заменяются заглушками, пароль сбрасывается,
    вход блокируется (`is_active=false`). Прогресс и история остаются, но
    обезличены (связь только по неизменному `user_id`). Требует пароль, чтобы
    чужой токен не мог удалить аккаунт.
    """
    if not await run_in_threadpool(
        verify_password, payload.password, current_user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный пароль: удаление отменено",
        )

    suffix = uuid4().hex[:12]
    current_user.username = f"deleted_{suffix}"
    current_user.email = f"deleted_{suffix}@invalid"
    current_user.hashed_password = await run_in_threadpool(hash_password, uuid4().hex)
    current_user.is_active = False
    current_user.last_active = datetime.utcnow()

    await record_audit(
        db,
        actor=current_user,
        action="user.self_deleted",
        entity_type="user",
        entity_id=current_user.id,
        request=request,
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
