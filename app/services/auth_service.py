import uuid

from app.core.logging import get_logger
from app.core.security import verify_password
from app.domain.exceptions import AuthenticationError
from app.models.document import User
from app.repositories.user_repository import UserRepository
from app.schemas.document import (
    LoginRequest,
    UserCreate,
)

logger = get_logger(__name__)


class AuthService:
    def __init__(self, user_repo: UserRepository) -> None:
        self._users = user_repo

    async def authenticate(self, credentials: LoginRequest) -> User:
        user = await self._users.find_by_username(credentials.username)
        if user is None or not verify_password(credentials.password, user.hashed_password):
            raise AuthenticationError("Incorrect username or password")
        return user

    async def register(self, data: UserCreate) -> User:
        user = await self._users.create(data)
        logger.info("user_registered", username=user.username, role=user.role)
        return user

    async def get_user_by_id(self, user_id: str) -> User | None:
        try:
            uid = uuid.UUID(user_id)
        except ValueError:
            return None
        return await self._users.find_by_id(uid)
