from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.auth_controller import AuthController
from app.controllers.document_controller import DocumentController
from app.controllers.health_controller import HealthController
from app.db.session import get_db_session
from app.repositories.document_repository import DocumentRepository
from app.repositories.outbox_repository import OutboxRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.document_service import DocumentService
from app.services.outbox_service import OutboxService

DBSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_auth_controller(session: DBSession) -> AuthController:
    return AuthController(AuthService(UserRepository(session)))


def get_document_controller(session: DBSession) -> DocumentController:
    return DocumentController(
        DocumentService(
            DocumentRepository(session),
            OutboxRepository(session),
        )
    )


def get_health_controller() -> HealthController:
    return HealthController(OutboxService())


AuthControllerDep = Annotated[AuthController, Depends(get_auth_controller)]
DocumentControllerDep = Annotated[DocumentController, Depends(get_document_controller)]
HealthControllerDep = Annotated[HealthController, Depends(get_health_controller)]
