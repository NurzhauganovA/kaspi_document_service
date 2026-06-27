"""
Locust load test for Document Processing Service.

Run (requires running stack + seeded users):
    locust -f scripts/locustfile.py --host=http://localhost:8000 \\
           --users 100 --spawn-rate 10 --run-time 120s --headless \\
           --html load_test_report.html

Target NFRs (from assignment):
  - median latency < 1s
  - 100 concurrent users
  - error rate < 0.1% (excluding empty queue 404)
"""

import random
import uuid
from datetime import (
    datetime,
    timedelta,
    timezone,
)

from locust import (
    HttpUser,
    between,
    events,
    task,
)
from locust.runners import MasterRunner


# ─── Helpers ─────────────────────────────────────────────────────────────────

OPERATOR_CREDS = [
    {"username": f"operator_{i}", "password": "Test1234!"}
    for i in range(1, 51)
]
SUPERVISOR_CREDS = [
    {"username": f"supervisor_{i}", "password": "Test1234!"}
    for i in range(1, 6)
]


class AuthMixin:
    """Provides login helper and token management."""

    token: str | None = None

    def login(self, credentials: dict) -> bool:
        with self.client.post(
            "/api/v1/auth/login",
            json={
                "username": credentials["username"],
                "password": credentials["password"],
            },
            catch_response=True,
            name="/api/v1/auth/login",
        ) as resp:
            if resp.status_code == 200:
                self.token = resp.json()["access_token"]
                return True
            resp.failure(f"Login failed: {resp.status_code} {resp.text}")
            return False

    @property
    def auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}


# ─── Operator scenario (80%) ──────────────────────────────────────────────────

class OperatorUser(AuthMixin, HttpUser):
    """
    Simulates an operator:
    1. Login (once on start)
    2. Claim document
    3. Make decision (accept 70% / reject 30%)
    """

    weight = 80
    wait_time = between(0.5, 2.0)
    claimed_document_id: str | None = None

    def on_start(self) -> None:
        creds = random.choice(OPERATOR_CREDS)
        self.login(creds)

    @task(3)
    def claim_document(self) -> None:
        if not self.token:
            self.login(random.choice(OPERATOR_CREDS))
            return

        with self.client.post(
            "/api/v1/documents/claim",
            headers=self.auth_headers,
            catch_response=True,
            name="/api/v1/documents/claim",
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                self.claimed_document_id = data["document"]["id"]
            elif resp.status_code == 404:
                # No documents in queue — not a failure
                resp.success()
                self.claimed_document_id = None
            elif resp.status_code == 401:
                resp.failure("Unauthorized")
                self.token = None
            else:
                resp.failure(f"Unexpected: {resp.status_code}")

    @task(2)
    def make_decision(self) -> None:
        if not self.token or not self.claimed_document_id:
            return

        action = random.choices(
            ["accepted", "rejected"], weights=[70, 30], k=1
        )[0]
        body: dict = {"action": action}
        if action == "rejected":
            body["rejection_reason"] = "Automated test rejection"

        doc_id = self.claimed_document_id
        self.claimed_document_id = None  # Reset before request to avoid double-decision

        with self.client.post(
            f"/api/v1/documents/{doc_id}/decision",
            json=body,
            headers=self.auth_headers,
            catch_response=True,
            name="/api/v1/documents/{id}/decision",
        ) as resp:
            if resp.status_code in (200, 422):
                resp.success()
            elif resp.status_code == 401:
                resp.failure("Unauthorized")
                self.token = None
            else:
                resp.failure(f"Unexpected: {resp.status_code} {resp.text[:200]}")


# ─── Supervisor scenario (20%) ────────────────────────────────────────────────

class SupervisorUser(AuthMixin, HttpUser):
    """
    Simulates a supervisor checking statistics.
    """

    weight = 20
    wait_time = between(2.0, 5.0)

    def on_start(self) -> None:
        creds = random.choice(SUPERVISOR_CREDS)
        self.login(creds)

    @task
    def get_statistics(self) -> None:
        if not self.token:
            self.login(random.choice(SUPERVISOR_CREDS))
            return

        now = datetime.now(timezone.utc)
        from_dt = (now - timedelta(hours=24)).isoformat()
        to_dt = now.isoformat()

        with self.client.get(
            "/api/v1/documents/statistics",
            params={"from_dt": from_dt, "to_dt": to_dt},
            headers=self.auth_headers,
            catch_response=True,
            name="/api/v1/documents/statistics",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 401:
                resp.failure("Unauthorized")
                self.token = None
            else:
                resp.failure(f"Unexpected: {resp.status_code}")

    @task
    def health_check(self) -> None:
        self.client.get("/api/v1/health", name="/api/v1/health")


# ─── Event hooks ──────────────────────────────────────────────────────────────

@events.init.add_listener
def on_locust_init(environment, **kwargs) -> None:  # type: ignore[no-untyped-def]
    if not isinstance(environment.runner, MasterRunner):
        print("📊 Locust initialized — targeting Document Processing Service")
