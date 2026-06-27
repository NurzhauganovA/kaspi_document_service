import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1 import api_router
from app.core.config import settings
from app.core.logging import (
    get_logger,
    setup_logging,
)
from app.core.redis import close_redis
from app.services.kafka_producer import (
    get_kafka_producer,
    stop_kafka_producer,
)
from app.workers.kafka_consumer import (
    run_consumer,
    stop_consumer,
)
from app.workers.outbox_worker import (
    start_outbox_worker,
    stop_outbox_worker,
)

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("application_starting", env=settings.APP_ENV)

    await get_kafka_producer()
    consumer_task = asyncio.create_task(run_consumer())
    await start_outbox_worker()

    logger.info("application_started")
    yield

    logger.info("application_stopping")
    await stop_consumer()
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass

    await stop_outbox_worker()
    await stop_kafka_producer()
    await close_redis()
    logger.info("application_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_TITLE,
        version=settings.APP_VERSION,
        docs_url="/docs" if settings.APP_ENV != "production" else None,
        redoc_url="/redoc" if settings.APP_ENV != "production" else None,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.APP_ENV != "production" else [],
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        start = time.perf_counter()
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            method=request.method,
            path=request.url.path,
        )
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        logger.info(
            "http_request",
            status_code=response.status_code,
            duration_ms=round(elapsed * 1000, 2),
        )
        response.headers["X-Process-Time"] = f"{elapsed:.4f}"
        return response

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> ORJSONResponse:
        # Let FastAPI handle HTTPException (404, 422, 401, etc.)
        if isinstance(exc, HTTPException):
            return ORJSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=exc.headers,
            )

        logger.exception("unhandled_exception", path=request.url.path, error=str(exc))
        return ORJSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

    app.include_router(api_router)

    Instrumentator(
        should_group_status_codes=True,
        excluded_handlers=["/health", "/metrics"],
    ).instrument(app).expose(app)

    return app


app = create_app()
