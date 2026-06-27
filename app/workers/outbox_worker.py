import asyncio

from app.core.logging import get_logger
from app.services.outbox_service import OutboxService

logger = get_logger(__name__)

_outbox_task: asyncio.Task[None] | None = None
_running = False


async def run_outbox_worker() -> None:
    global _running
    _running = True
    service = OutboxService()
    logger.info("outbox_worker_started")

    while _running:
        try:
            await service.process_batch()
        except Exception as exc:
            logger.exception("outbox_worker_error", error=str(exc))
        await asyncio.sleep(1)


async def start_outbox_worker() -> asyncio.Task[None]:
    global _outbox_task
    _outbox_task = asyncio.create_task(run_outbox_worker())
    return _outbox_task


async def stop_outbox_worker() -> None:
    global _running, _outbox_task
    _running = False
    if _outbox_task:
        _outbox_task.cancel()
        try:
            await _outbox_task
        except asyncio.CancelledError:
            pass
        _outbox_task = None
    logger.info("outbox_worker_stopped")
