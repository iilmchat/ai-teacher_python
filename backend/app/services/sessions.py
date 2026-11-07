"""Активные сессии и их отзыв (S45-005).

Сессия — строка `user_sessions`, связанная с парой токенов через `jti`.
`jti` ротируется при каждом refresh (старый refresh-токен перестаёт
работать), поэтому список сессий всегда отражает действующие токены.

`token_version` пользователя — грубый рубильник для всех refresh-токенов
(смена пароля, «выйти на всех устройствах»); точечный отзыв сессии версию
не меняет.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.models.user import User, UserSession


def request_details(request: Request) -> tuple[str | None, str | None]:
    """User-Agent и IP запроса (для списка сессий; поля обрезаются)"""
    user_agent = request.headers.get("user-agent")
    forwarded = request.headers.get("x-forwarded-for")
    ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else None)
    )
    return (
        user_agent[:255] if user_agent else None,
        ip[:64] if ip else None,
    )


def current_jti(request: Request) -> str | None:
    """`jti` текущей сессии из access-токена (None — старый токен без jti)"""
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    payload = decode_token(header[7:])
    jti = (payload or {}).get("jti")
    return str(jti) if jti else None


async def create_session(
    db: AsyncSession,
    user_id: UUID,
    *,
    jti: str | None = None,
    user_agent: str | None = None,
    ip: str | None = None,
) -> str:
    """Создать строку сессии и вернуть `jti`"""
    session_jti = jti or str(uuid4())
    db.add(
        UserSession(
            user_id=user_id,
            jti=session_jti,
            user_agent=user_agent,
            ip=ip,
        )
    )
    await db.commit()
    return session_jti


async def start_session(
    db: AsyncSession, user: User, request: Request, *, jti: str | None = None
) -> str:
    """Создать сессию для нового входа/устройства и вернуть `jti`"""
    user_agent, ip = request_details(request)
    return await create_session(
        db, user.id, jti=jti, user_agent=user_agent, ip=ip
    )


async def rotate_session(db: AsyncSession, user: User, jti: str | None) -> str:
    """Проверить сессию по `jti` и выдать новый (ротация refresh-токена).

    Токены без `jti` (выданные до S45-005) не отклоняются: для них
    заводится новая сессия — deploy не разлогинивает активных пользователей.
    """
    new_jti = str(uuid4())
    if jti is None:
        await create_session(db, user.id, jti=new_jti)
        return new_jti

    session = (
        (
            await db.execute(
                select(UserSession).where(
                    UserSession.jti == jti,
                    UserSession.user_id == user.id,
                )
            )
        )
        .scalars()
        .one_or_none()
    )
    if session is None or session.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    session.jti = new_jti
    session.last_used_at = datetime.utcnow()
    await db.commit()
    return new_jti


async def list_sessions(db: AsyncSession, user_id: UUID) -> list[UserSession]:
    """Действующие (не отозванные) сессии пользователя, свежие сверху"""
    return list(
        (
            await db.execute(
                select(UserSession)
                .where(
                    UserSession.user_id == user_id,
                    UserSession.revoked_at.is_(None),
                )
                .order_by(UserSession.last_used_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def revoke_session(
    db: AsyncSession, user_id: UUID, session_id: UUID
) -> UserSession | None:
    """Отозвать конкретную сессию (None — не найдена/чужая)"""
    session = await db.get(UserSession, session_id)
    if (
        session is None
        or session.user_id != user_id
        or session.revoked_at is not None
    ):
        return None
    session.revoked_at = datetime.utcnow()
    await db.commit()
    return session


async def revoke_all_sessions(db: AsyncSession, user_id: UUID) -> int:
    """Отозвать все действующие сессии пользователя"""
    result = await db.execute(
        update(UserSession)
        .where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.utcnow())
    )
    await db.commit()
    return int(result.rowcount or 0)
