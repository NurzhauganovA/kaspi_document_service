from sqlalchemy import text

from app.core.config import settings
from app.core.redis import get_redis
from app.db.session import AsyncSessionFactory
from app.schemas.document import HealthResponse
from app.services.outbox_service import OutboxService


class HealthController:
    def __init__(self, outbox_service: OutboxService) -> None:
        self._outbox = outbox_service

    async def check(self) -> HealthResponse:
        db_status = await self._check_database()
        redis_status = await self._check_redis()
        kafka_status = await self._outbox.health_check()

        components = [db_status, redis_status, kafka_status]
        overall = "ok" if all(s == "ok" for s in components) else "degraded"

        return HealthResponse(
            status=overall,
            db=db_status,
            redis=redis_status,
            kafka=kafka_status,
            version=settings.APP_VERSION,
        )

    async def _check_database(self) -> str:
        try:
            async with AsyncSessionFactory() as session:
                await session.execute(text("SELECT 1"))
            return "ok"
        except Exception as exc:
            return f"error: {exc}"

    async def _check_redis(self) -> str:
        try:
            redis = await get_redis()
            await redis.ping()
            return "ok"
        except Exception as exc:
            return f"error: {exc}"
