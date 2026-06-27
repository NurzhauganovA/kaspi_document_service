import uuid
from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest
from httpx import AsyncClient

from app.models.document import User
from tests.helpers import (
    auth_header,
    in_progress_document,
)


class TestAuthEndpoints:
    async def test_login_returns_token(self, client: AsyncClient, operator: User) -> None:
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": operator.username, "password": "Test1234!"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert "access_token" in body

    async def test_login_wrong_password(self, client: AsyncClient, operator: User) -> None:
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": operator.username, "password": "wrong"},
        )
        assert response.status_code == 401

    async def test_register_requires_admin(self, client: AsyncClient, operator: User) -> None:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "new_user",
                "email": "new@test.local",
                "password": "Test1234!",
                "role": "operator",
            },
            headers=auth_header(operator),
        )
        assert response.status_code == 403

    async def test_admin_can_register(self, client: AsyncClient, admin: User) -> None:
        username = f"new_{uuid.uuid4().hex[:6]}"
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": username,
                "email": f"{username}@test.local",
                "password": "Test1234!",
                "role": "operator",
            },
            headers=auth_header(admin),
        )
        assert response.status_code == 201
        assert response.json()["username"] == username


class TestDocumentEndpoints:
    async def test_claim_assigns_pending_document(
        self,
        client: AsyncClient,
        operator: User,
        pending_document,
    ) -> None:
        response = await client.post(
            "/api/v1/documents/claim",
            headers=auth_header(operator),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["document"]["status"] == "in_progress"
        assert body["document"]["assigned_to_id"] == str(operator.id)

    async def test_claim_empty_queue_returns_404(self, client: AsyncClient, operator: User) -> None:
        response = await client.post(
            "/api/v1/documents/claim",
            headers=auth_header(operator),
        )
        assert response.status_code == 404

    async def test_accept_document(
        self,
        client: AsyncClient,
        session,
        operator: User,
    ) -> None:
        doc = in_progress_document(session, operator)
        await session.flush()

        response = await client.post(
            f"/api/v1/documents/{doc.id}/decision",
            json={"action": "accepted"},
            headers=auth_header(operator),
        )
        assert response.status_code == 200
        assert response.json()["document"]["status"] == "accepted"

    async def test_reject_requires_reason(
        self,
        client: AsyncClient,
        session,
        operator: User,
    ) -> None:
        doc = in_progress_document(session, operator)
        await session.flush()

        response = await client.post(
            f"/api/v1/documents/{doc.id}/decision",
            json={"action": "rejected"},
            headers=auth_header(operator),
        )
        assert response.status_code == 422

    async def test_operator_cannot_view_statistics(
        self,
        client: AsyncClient,
        operator: User,
    ) -> None:
        now = datetime.now(timezone.utc)
        response = await client.get(
            "/api/v1/documents/statistics",
            params={
                "from_dt": (now - timedelta(hours=1)).isoformat(),
                "to_dt": now.isoformat(),
            },
            headers=auth_header(operator),
        )
        assert response.status_code == 403

    async def test_supervisor_can_view_statistics(
        self,
        client: AsyncClient,
        supervisor: User,
    ) -> None:
        now = datetime.now(timezone.utc)
        response = await client.get(
            "/api/v1/documents/statistics",
            params={
                "from_dt": (now - timedelta(hours=1)).isoformat(),
                "to_dt": now.isoformat(),
            },
            headers=auth_header(supervisor),
        )
        assert response.status_code == 200
        assert "total" in response.json()

    async def test_unauthenticated_claim_returns_401(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/documents/claim")
        assert response.status_code == 401
