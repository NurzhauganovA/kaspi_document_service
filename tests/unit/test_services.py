import uuid
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from unittest.mock import AsyncMock

import pytest

from app.core.security import hash_password
from app.domain.exceptions import (
    AuthenticationError,
    EmptyQueueError,
    InvalidDocumentStateError,
)
from app.models.document import (
    Document,
    DocumentStatusEnum,
    RoleEnum,
    User,
)
from app.schemas.document import (
    DecisionRequest,
    LoginRequest,
    StatsPeriodRequest,
)
from app.services.auth_service import AuthService
from app.services.document_service import DocumentService


@pytest.fixture
def operator() -> User:
    return User(
        id=uuid.uuid4(),
        username="op",
        email="op@test.local",
        hashed_password="hash",
        role=RoleEnum.OPERATOR,
        is_active=True,
    )


class TestAuthService:
    async def test_authenticate_success(self, operator: User) -> None:
        user_repo = AsyncMock()
        user_repo.find_by_username.return_value = operator

        operator.hashed_password = hash_password("Test1234!")
        service = AuthService(user_repo)

        user = await service.authenticate(
            LoginRequest(username="operator", password="Test1234!")
        )
        assert user is operator

    async def test_authenticate_wrong_password_raises(self, operator: User) -> None:
        operator.hashed_password = hash_password("Test1234!")
        user_repo = AsyncMock()
        user_repo.find_by_username.return_value = operator
        service = AuthService(user_repo)

        with pytest.raises(AuthenticationError):
            await service.authenticate(LoginRequest(username="operator", password="wrong1"))


class TestDocumentService:
    async def test_claim_next_raises_when_queue_empty(self, operator: User) -> None:
        doc_repo = AsyncMock()
        doc_repo.find_next_pending.return_value = None
        outbox_repo = AsyncMock()
        service = DocumentService(doc_repo, outbox_repo)

        with pytest.raises(EmptyQueueError):
            await service.claim_next(operator)

    async def test_claim_next_assigns_operator(self, operator: User) -> None:
        document = Document(
            external_id="ext-1",
            source_topic="documents.incoming",
            payload={"x": 1},
            status=DocumentStatusEnum.PENDING,
        )
        doc_repo = AsyncMock()
        doc_repo.find_next_pending.return_value = document
        outbox_repo = AsyncMock()
        service = DocumentService(doc_repo, outbox_repo)

        result = await service.claim_next(operator)
        assert result.status == DocumentStatusEnum.IN_PROGRESS
        assert result.assigned_to_id == operator.id
        assert result.assigned_at is not None

    async def test_make_decision_creates_outbox_event(self, operator: User) -> None:
        document = Document(
            id=uuid.uuid4(),
            external_id="ext-2",
            source_topic="documents.incoming",
            payload={"x": 2},
            status=DocumentStatusEnum.IN_PROGRESS,
            assigned_to_id=operator.id,
            assigned_at=datetime.now(timezone.utc),
        )
        doc_repo = AsyncMock()
        doc_repo.find_in_progress_for_operator.return_value = document
        outbox_repo = AsyncMock()
        service = DocumentService(doc_repo, outbox_repo)

        decision = DecisionRequest(action=DocumentStatusEnum.ACCEPTED)
        result = await service.make_decision(document.id, operator, decision)

        assert result.status == DocumentStatusEnum.ACCEPTED
        outbox_repo.create_event.assert_awaited_once()

    async def test_make_decision_invalid_state_raises(self, operator: User) -> None:
        doc_repo = AsyncMock()
        doc_repo.find_in_progress_for_operator.return_value = None
        outbox_repo = AsyncMock()
        service = DocumentService(doc_repo, outbox_repo)

        with pytest.raises(InvalidDocumentStateError):
            await service.make_decision(
                uuid.uuid4(),
                operator,
                DecisionRequest(action=DocumentStatusEnum.ACCEPTED),
            )

    async def test_statistics_aggregates_counts(self, operator: User) -> None:
        doc_repo = AsyncMock()
        doc_repo.count_by_status.return_value = {
            DocumentStatusEnum.PENDING: 2,
            DocumentStatusEnum.ACCEPTED: 3,
        }
        doc_repo.average_processing_seconds.return_value = 12.5
        doc_repo.top_operators.return_value = [{"username": "op", "total": 3, "accepted": 2}]
        outbox_repo = AsyncMock()
        service = DocumentService(doc_repo, outbox_repo)

        now = datetime.now(timezone.utc)
        stats = await service.get_statistics(
            StatsPeriodRequest(from_dt=now - timedelta(hours=1), to_dt=now)
        )

        assert stats.total == 5
        assert stats.pending == 2
        assert stats.accepted == 3
        assert stats.avg_processing_seconds == 12.5
