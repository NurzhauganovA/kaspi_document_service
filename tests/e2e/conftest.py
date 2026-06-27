import os
import uuid

import pytest
from httpx import (
    ASGITransport,
    AsyncClient,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.models.document import (
    Document,
    DocumentStatusEnum,
    RoleEnum,
    User,
)

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/documents_test",
)


@pytest.fixture(scope="session")
async def engine():
    _engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await _engine.dispose()


@pytest.fixture
async def session(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as _session:
        yield _session
        await _session.rollback()


@pytest.fixture
async def client(session: AsyncSession):
    async def override_db():
        yield session

    app.dependency_overrides[get_db_session] = override_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def operator(session: AsyncSession) -> User:
    user = User(
        username=f"operator_{uuid.uuid4().hex[:8]}",
        email=f"op_{uuid.uuid4().hex[:8]}@test.local",
        hashed_password=hash_password("Test1234!"),
        role=RoleEnum.OPERATOR,
    )
    session.add(user)
    await session.flush()
    return user


@pytest.fixture
async def supervisor(session: AsyncSession) -> User:
    user = User(
        username=f"supervisor_{uuid.uuid4().hex[:8]}",
        email=f"sup_{uuid.uuid4().hex[:8]}@test.local",
        hashed_password=hash_password("Test1234!"),
        role=RoleEnum.SUPERVISOR,
    )
    session.add(user)
    await session.flush()
    return user


@pytest.fixture
async def admin(session: AsyncSession) -> User:
    user = User(
        username=f"admin_{uuid.uuid4().hex[:8]}",
        email=f"admin_{uuid.uuid4().hex[:8]}@test.local",
        hashed_password=hash_password("Admin1234!"),
        role=RoleEnum.ADMIN,
    )
    session.add(user)
    await session.flush()
    return user


@pytest.fixture
async def pending_document(session: AsyncSession) -> Document:
    doc = Document(
        external_id=str(uuid.uuid4()),
        source_topic="documents.incoming",
        payload={"type": "invoice", "amount": 1000},
        status=DocumentStatusEnum.PENDING,
    )
    session.add(doc)
    await session.flush()
    return doc
