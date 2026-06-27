import uuid
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
)

from app.models.document import (
    DocumentStatusEnum,
    RoleEnum,
)


# ─── Auth ────────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"username": "admin", "password": "Admin1234!"},
        }
    )

    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6)


# ─── User ─────────────────────────────────────────────────────────────────────

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    full_name: str | None = None
    role: RoleEnum = RoleEnum.OPERATOR


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ─── Document ─────────────────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    external_id: str
    source_topic: str
    payload: dict
    status: DocumentStatusEnum
    assigned_to_id: uuid.UUID | None
    assigned_at: datetime | None
    decision_at: datetime | None
    rejection_reason: str | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document: DocumentResponse
    message: str = "Document claimed successfully"


class DecisionRequest(BaseModel):
    action: DocumentStatusEnum = Field(
        ...,
        description="Must be 'accepted' or 'rejected'",
    )
    rejection_reason: str | None = Field(
        None,
        max_length=1024,
        description="Required when action is 'rejected'",
    )

    def model_post_init(self, __context: object) -> None:
        if self.action == DocumentStatusEnum.REJECTED and not self.rejection_reason:
            raise ValueError("rejection_reason is required when action is 'rejected'")
        if self.action not in (DocumentStatusEnum.ACCEPTED, DocumentStatusEnum.REJECTED):
            raise ValueError("action must be 'accepted' or 'rejected'")


class DecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document: DocumentResponse
    message: str


# ─── Statistics ───────────────────────────────────────────────────────────────

class StatsPeriodRequest(BaseModel):
    from_dt: datetime = Field(..., description="Start of period (UTC)")
    to_dt: datetime = Field(..., description="End of period (UTC)")

    def model_post_init(self, __context: object) -> None:
        if self.from_dt >= self.to_dt:
            raise ValueError("from_dt must be before to_dt")


class DocumentStats(BaseModel):
    total: int
    pending: int
    in_progress: int
    accepted: int
    rejected: int
    avg_processing_seconds: float | None
    top_operators: list[dict]


# ─── Health ───────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    db: str
    redis: str
    kafka: str
    version: str
