from app.models.document import User
from app.schemas.document import (
    LoginRequest,
    UserCreate,
)
from app.services.auth_service import AuthService


class AuthController:
    def __init__(self, auth_service: AuthService) -> None:
        self._auth = auth_service

    async def login(self, credentials: LoginRequest) -> User:
        return await self._auth.authenticate(credentials)

    async def register(self, data: UserCreate) -> User:
        return await self._auth.register(data)
