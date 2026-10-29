"""
Authentication API endpoints
"""
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_active_user,
    get_current_user,
    hash_password,
    verify_password,
)
from app.db.database import get_db
from app.db.repositories.user import UserRepository
from app.models.user import User, UserLevel, UserRole
from app.schemas.user import UserCreate, UserResponse, UserUpdate

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

    user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hash_password(user_data.password),
        role=user_data.role or UserRole.STUDENT,
        level=user_data.level or UserLevel.BASIC,
    )
    return await user_repo.create(user)


@router.post("/login")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
) -> dict[str, Any]:
    """Вход по username или email; возвращает пару токенов"""
    user_repo = UserRepository(db)

    user = await user_repo.get_by_username(form_data.username)
    if not user:
        user = await user_repo.get_by_email(form_data.username)

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    await user_repo.update(user.id, last_active=datetime.utcnow())

    return {
        "access_token": create_access_token(data={"sub": str(user.id)}),
        "refresh_token": create_refresh_token(data={"sub": str(user.id)}),
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
    user_id = _user_id_from_payload(decode_token(refresh_token))
    user = await UserRepository(db).get(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "access_token": create_access_token(data={"sub": str(user.id)}),
        "refresh_token": create_refresh_token(data={"sub": str(user.id)}),
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

    updated_user = await user_repo.update(current_user.id, **update_dict)
    if updated_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return updated_user
