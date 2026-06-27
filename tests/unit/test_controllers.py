import uuid
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from unittest.mock import AsyncMock

import pytest

from app.controllers.document_controller import DocumentController
from app.domain.exceptions import (
    EmptyQueueError,
    InvalidDocumentStateError,
)
from app.models.document import (
    DocumentStatusEnum,
    RoleEnum,
    User,
)
from app.schemas.document import (
    DecisionRequest,
    DocumentStats,
    StatsPeriodRequest,
)


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


class TestDocumentController:
    async def test_claim_propagates_empty_queue(self, operator: User) -> None:
        service = AsyncMock()
        service.claim_next.side_effect = EmptyQueueError("empty")
        controller = DocumentController(service)

        with pytest.raises(EmptyQueueError):
            await controller.claim(operator)

    async def test_decision_propagates_invalid_state(self, operator: User) -> None:
        service = AsyncMock()
        service.make_decision.side_effect = InvalidDocumentStateError("bad state")
        controller = DocumentController(service)

        with pytest.raises(InvalidDocumentStateError):
            await controller.make_decision(
                uuid.uuid4(),
                operator,
                DecisionRequest(action=DocumentStatusEnum.ACCEPTED),
            )

    async def test_statistics_returns_service_result(self, operator: User) -> None:
        service = AsyncMock()
        stats = DocumentStats(
            total=0,
            pending=0,
            in_progress=0,
            accepted=0,
            rejected=0,
            avg_processing_seconds=None,
            top_operators=[],
        )
        service.get_statistics.return_value = stats
        controller = DocumentController(service)

        now = datetime.now(timezone.utc)
        result = await controller.statistics(
            StatsPeriodRequest(from_dt=now - timedelta(hours=1), to_dt=now)
        )
        assert result.total == 0
