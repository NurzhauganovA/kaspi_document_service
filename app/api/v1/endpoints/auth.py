from typing import Annotated

from fastapi import (
    APIRouter,
    status,
)

from app.api.http_errors import raise_for_domain
from app.core.config import settings
from app.core.security import create_access_token
from app.dependencies.auth import AdminUser
from app.dependencies.controllers import AuthControllerDep
from app.domain.exceptions import DomainError
from app.schemas.document import (
    LoginRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login with username and password, receive JWT",
)
async def login(
    credentials: LoginRequest,
    controller: AuthControllerDep,
) -> TokenResponse:
    try:
        user = await controller.login(credentials)
    except DomainError as exc:
        raise_for_domain(exc)

    token = create_access_token(
        subject=str(user.id),
        extra_claims={"role": user.role, "username": user.username},
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user (admin only, JWT required)",
)
async def register(
    data: UserCreate,
    controller: AuthControllerDep,
    _: AdminUser,
) -> UserResponse:
    user = await controller.register(data)
    return UserResponse.model_validate(user)
