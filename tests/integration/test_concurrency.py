import asyncio
import uuid

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from app.models.document import (
    Document,
    DocumentStatusEnum,
    RoleEnum,
    User,
)
from app.repositories.document_repository import DocumentRepository
from app.repositories.outbox_repository import OutboxRepository
from app.services.document_service import DocumentService


@pytest.mark.integration
class TestConcurrentClaims:
    async def test_skip_locked_prevents_double_claim(self, engine) -> None:
        """Two sessions claiming concurrently must receive different documents."""
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        operator_a = User(
            username=f"a_{uuid.uuid4().hex[:6]}",
            email=f"a_{uuid.uuid4().hex[:6]}@test.local",
            hashed_password="hash",
            role=RoleEnum.OPERATOR,
        )
        operator_b = User(
            username=f"b_{uuid.uuid4().hex[:6]}",
            email=f"b_{uuid.uuid4().hex[:6]}@test.local",
            hashed_password="hash",
            role=RoleEnum.OPERATOR,
        )

        async with factory() as setup_session:
            async with setup_session.begin():
                setup_session.add_all([operator_a, operator_b])
                for _ in range(2):
                    setup_session.add(
                        Document(
                            external_id=str(uuid.uuid4()),
                            source_topic="documents.incoming",
                            payload={"n": 1},
                            status=DocumentStatusEnum.PENDING,
                        )
                    )

        async def claim(operator: User) -> uuid.UUID | None:
            async with factory() as session:
                async with session.begin():
                    service = DocumentService(
                        DocumentRepository(session),
                        OutboxRepository(session),
                    )
                    document = await service.claim_next(operator)
                    return document.id

        doc_a, doc_b = await asyncio.gather(claim(operator_a), claim(operator_b))
        assert doc_a is not None
        assert doc_b is not None
        assert doc_a != doc_b
