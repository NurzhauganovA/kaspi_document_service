from fastapi import APIRouter

from app.dependencies.controllers import HealthControllerDep
from app.schemas.document import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, include_in_schema=True)
async def health_check(controller: HealthControllerDep) -> HealthResponse:
    return await controller.check()
