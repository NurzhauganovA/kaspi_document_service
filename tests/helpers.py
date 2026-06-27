import uuid
from datetime import (
    datetime,
    timezone,
)

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.document import (
    Document,
    DocumentStatusEnum,
    User,
)


def auth_header(user: User) -> dict[str, str]:
    token = create_access_token(str(user.id), {"role": user.role, "username": user.username})
    return {"Authorization": f"Bearer {token}"}


def in_progress_document(session: AsyncSession, operator: User) -> Document:
    doc = Document(
        external_id=str(uuid.uuid4()),
        source_topic="documents.incoming",
        payload={"type": "contract"},
        status=DocumentStatusEnum.IN_PROGRESS,
        assigned_to_id=operator.id,
        assigned_at=datetime.now(timezone.utc),
    )
    session.add(doc)
    return doc
