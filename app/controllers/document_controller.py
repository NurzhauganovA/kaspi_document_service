import uuid

from app.models.document import (
    Document,
    User,
)
from app.schemas.document import (
    DecisionRequest,
    DocumentStats,
    StatsPeriodRequest,
)
from app.services.document_service import DocumentService


class DocumentController:
    def __init__(self, document_service: DocumentService) -> None:
        self._documents = document_service

    async def claim(self, operator: User) -> Document:
        return await self._documents.claim_next(operator)

    async def make_decision(
        self,
        document_id: uuid.UUID,
        operator: User,
        decision: DecisionRequest,
    ) -> Document:
        return await self._documents.make_decision(document_id, operator, decision)

    async def statistics(self, period: StatsPeriodRequest) -> DocumentStats:
        return await self._documents.get_statistics(period)
