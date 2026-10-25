import asyncio
import logging
import signal

from app.worker.scheduler import JobScheduler  # Adjust if needed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


async def main() -> None:
    scheduler = JobScheduler()

    logger.info(
        "Starting scheduler worker: worker_id=%s",
        scheduler.worker_id,
    )

    try:
        await scheduler.run()
    except asyncio.CancelledError:
        logger.info(
            "Scheduler worker stopped: worker_id=%s",
            scheduler.worker_id,
        )
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass