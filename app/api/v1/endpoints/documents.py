import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    status,
)

from app.api.http_errors import raise_for_domain
from app.dependencies.auth import (
    OperatorUser,
    SupervisorUser,
)
from app.dependencies.controllers import DocumentControllerDep
from app.domain.exceptions import DomainError
from app.schemas.document import (
    ClaimResponse,
    DecisionRequest,
    DecisionResponse,
    DocumentResponse,
    DocumentStats,
    StatsPeriodRequest,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/claim",
    response_model=ClaimResponse,
    status_code=status.HTTP_200_OK,
    summary="Claim the next pending document from the queue",
)
async def claim_document(
    controller: DocumentControllerDep,
    operator: OperatorUser,
) -> ClaimResponse:
    try:
        document = await controller.claim(operator)
    except DomainError as exc:
        raise_for_domain(exc)
    return ClaimResponse(document=DocumentResponse.model_validate(document))


@router.post(
    "/{document_id}/decision",
    response_model=DecisionResponse,
    status_code=status.HTTP_200_OK,
    summary="Accept or reject a claimed document",
)
async def make_decision(
    document_id: uuid.UUID,
    decision: DecisionRequest,
    controller: DocumentControllerDep,
    operator: OperatorUser,
) -> DecisionResponse:
    try:
        document = await controller.make_decision(document_id, operator, decision)
    except DomainError as exc:
        raise_for_domain(exc)
    return DecisionResponse(
        document=DocumentResponse.model_validate(document),
        message=f"Document {decision.action} successfully",
    )


@router.get(
    "/statistics",
    response_model=DocumentStats,
    status_code=status.HTTP_200_OK,
    summary="Get document processing statistics for a time range",
)
async def get_statistics(
    period: Annotated[StatsPeriodRequest, Depends()],
    controller: DocumentControllerDep,
    _: SupervisorUser,
) -> DocumentStats:
    return await controller.statistics(period)
