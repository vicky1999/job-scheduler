import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.database import AsyncSessionLocal
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.job.models import Job
from app.api.tenant.models import Tenant

from app.api.job.models import Job
from app.api.tenant.models import Tenant


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


TOTAL_JOBS = 50
TENANT_COUNT = 3

HANDLERS = [
    "print",
    "fibonacci",
    "sleep",
    "sleep_random_failure",
    "error",
]

async def create_tenants(session: AsyncSession) -> list[Tenant]:
    run_id = uuid4().hex[:8]

    tenants = [
        Tenant(name=f"test-tenant-{run_id}-{i}")
        for i in range(1, TENANT_COUNT + 1)
    ]

    session.add_all(tenants)
    await session.commit()

    for tenant in tenants:
        await session.refresh(tenant)
        logger.info(
            "Tenant created: id=%s, name=%s",
            tenant.id,
            tenant.name,
        )

    return tenants

def random_payload(handler: str) -> dict:
    if handler == "print":
        return {"message": f"Test message {random.randint(1, 999)}"}

    if handler == "fibonacci":
        return {"n": random.randint(1, 9)}

    if handler in ("sleep", "sleep_random_failure"):
        return {"seconds": random.randint(1, 9)}

    if handler == "error":
        return {"exception": "Test Exception"}

    raise ValueError(f"Unknown handler: {handler}")


def generate_jobs(tenants):
    """Generate jobs without persisting them yet."""
    now = datetime.now(timezone.utc)
    jobs = []

    for _ in range(TOTAL_JOBS):
        handler = random.choice(HANDLERS)
        tenant = random.choice(tenants)

        jobs.append(
            Job(
                tenant_id=tenant.id,
                handler=handler,
                payload=random_payload(handler),
                scheduled_at=now + timedelta(
                    seconds=random.randint(0, 9)
                ),
            )
        )

    return jobs


async def seed_data():
    async with AsyncSessionLocal() as session:
        tenants = await create_tenants(session)

        jobs = generate_jobs(tenants)
        session.add_all(jobs)
        await session.commit()

        for job in jobs:
            await session.refresh(job)

        logger.info("Created %d jobs", len(jobs))

        for tenant in tenants:
            count = sum(
                job.tenant_id == tenant.id for job in jobs
            )
            logger.info(
                "Tenant id=%s has %d jobs",
                tenant.id,
                count,
            )


if __name__ == "__main__":
    asyncio.run(seed_data())