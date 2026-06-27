import uuid
from datetime import (
    datetime,
    timezone,
)
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.exceptions import (
    EmptyQueueError,
    InvalidDocumentStateError,
)
from app.models.document import (
    Document,
    DocumentStatusEnum,
    User,
)
from app.repositories.document_repository import DocumentRepository
from app.repositories.outbox_repository import OutboxRepository
from app.schemas.document import (
    DecisionRequest,
    DocumentStats,
    StatsPeriodRequest,
)

logger = get_logger(__name__)


class DocumentService:
    def __init__(
        self,
        document_repo: DocumentRepository,
        outbox_repo: OutboxRepository,
    ) -> None:
        self._documents = document_repo
        self._outbox = outbox_repo

    async def claim_next(self, operator: User) -> Document:
        """
        Assign the oldest pending document to the operator.
        Uses SELECT FOR UPDATE SKIP LOCKED — safe across concurrent workers.
        """
        document = await self._documents.find_next_pending()
        if document is None:
            raise EmptyQueueError("No pending documents in queue")

        now = datetime.now(timezone.utc)
        document.status = DocumentStatusEnum.IN_PROGRESS
        document.assigned_to_id = operator.id
        document.assigned_at = now
        document.updated_at = now

        logger.info(
            "document_claimed",
            document_id=str(document.id),
            operator_id=str(operator.id),
        )
        return document

    async def make_decision(
        self,
        document_id: uuid.UUID,
        operator: User,
        decision: DecisionRequest,
    ) -> Document:
        document = await self._documents.find_in_progress_for_operator(
            document_id, operator.id
        )
        if document is None:
            raise InvalidDocumentStateError(
                f"Document {document_id} not found, not yours, or not in progress"
            )

        now = datetime.now(timezone.utc)
        document.status = decision.action
        document.decision_at = now
        document.updated_at = now
        if decision.action == DocumentStatusEnum.REJECTED:
            document.rejection_reason = decision.rejection_reason

        await self._outbox.create_event(
            aggregate_id=document.id,
            topic=settings.KAFKA_OUTPUT_TOPIC,
            key=str(document.id),
            payload=self._build_output_message(document),
        )

        logger.info(
            "document_decision",
            document_id=str(document.id),
            action=decision.action,
            operator_id=str(operator.id),
        )
        return document

    async def get_statistics(self, period: StatsPeriodRequest) -> DocumentStats:
        counts = await self._documents.count_by_status(period.from_dt, period.to_dt)
        avg_seconds = await self._documents.average_processing_seconds(
            period.from_dt, period.to_dt
        )
        top_operators = await self._documents.top_operators(
            period.from_dt, period.to_dt
        )
        total = sum(counts.values())

        return DocumentStats(
            total=total,
            pending=counts.get(DocumentStatusEnum.PENDING, 0),
            in_progress=counts.get(DocumentStatusEnum.IN_PROGRESS, 0),
            accepted=counts.get(DocumentStatusEnum.ACCEPTED, 0),
            rejected=counts.get(DocumentStatusEnum.REJECTED, 0),
            avg_processing_seconds=avg_seconds,
            top_operators=top_operators,
        )

    @staticmethod
    def _build_output_message(document: Document) -> dict[str, Any]:
        return {
            "document_id": str(document.id),
            "external_id": document.external_id,
            "status": document.status.value,
            "decision_at": document.decision_at.isoformat() if document.decision_at else None,
            "assigned_to_id": str(document.assigned_to_id) if document.assigned_to_id else None,
            "rejection_reason": document.rejection_reason,
            "payload": document.payload,
        }
