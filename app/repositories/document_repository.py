import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    case,
    func,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import (
    Document,
    DocumentStatusEnum,
    User,
)


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_next_pending(self) -> Document | None:
        stmt = (
            select(Document)
            .where(Document.status == DocumentStatusEnum.PENDING)
            .order_by(Document.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_in_progress_for_operator(
        self, document_id: uuid.UUID, operator_id: uuid.UUID
    ) -> Document | None:
        stmt = (
            select(Document)
            .where(
                Document.id == document_id,
                Document.assigned_to_id == operator_id,
                Document.status == DocumentStatusEnum.IN_PROGRESS,
            )
            .with_for_update()
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def bulk_insert_pending(self, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        stmt = (
            insert(Document)
            .values(records)
            .on_conflict_do_nothing(constraint="uq_document_external")
        )
        await self._session.execute(stmt)

    async def count_by_status(
        self, from_dt: datetime, to_dt: datetime
    ) -> dict[str, int]:
        stmt = (
            select(Document.status, func.count(Document.id).label("cnt"))
            .where(Document.created_at >= from_dt, Document.created_at <= to_dt)
            .group_by(Document.status)
        )
        result = await self._session.execute(stmt)
        return {row.status: row.cnt for row in result}

    async def average_processing_seconds(
        self, from_dt: datetime, to_dt: datetime
    ) -> float | None:
        stmt = select(
            func.avg(
                func.extract("epoch", Document.decision_at - Document.assigned_at)
            )
        ).where(
            Document.created_at >= from_dt,
            Document.created_at <= to_dt,
            Document.decision_at.isnot(None),
            Document.assigned_at.isnot(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def top_operators(
        self, from_dt: datetime, to_dt: datetime, limit: int = 10
    ) -> list[dict[str, Any]]:
        accepted_count = func.sum(
            case((Document.status == DocumentStatusEnum.ACCEPTED, 1), else_=0)
        ).label("accepted")

        stmt = (
            select(
                User.username,
                func.count(Document.id).label("total"),
                accepted_count,
            )
            .join(User, Document.assigned_to_id == User.id)
            .where(
                Document.created_at >= from_dt,
                Document.created_at <= to_dt,
                Document.status.in_(
                    [DocumentStatusEnum.ACCEPTED, DocumentStatusEnum.REJECTED]
                ),
            )
            .group_by(User.username)
            .order_by(text("total DESC"))
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [
            {"username": row.username, "total": row.total, "accepted": row.accepted or 0}
            for row in result
        ]
