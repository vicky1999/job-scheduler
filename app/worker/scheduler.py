import asyncio
import logging

from sqlalchemy import update

from app.worker.handlers import execute_handler
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import case, exists, select, update, cast

from app.api.job.models import Job, JobStatus
from app.api.tenant.models import Tenant
from app.core.database import AsyncSessionLocal
from app.core.settings import settings

logger = logging.getLogger(__name__)

class JobScheduler:
    def __init__(self) -> None:
        # Stable identity for this scheduler process.
        self.worker_id: UUID = uuid4()

        # In-memory cursor for best-effort tenant fairness.
        self._last_tenant_id: UUID | None = None

    async def claim_next_job(self) -> Job | None:
        now = datetime.now(timezone.utc)

        # Select the next eligible job, respecting tenant round-robin order.
        candidate = (
            select(Job.id)
            .join(Tenant, Tenant.id == Job.tenant_id)
            .where(
                Job.status == JobStatus.PENDING,
                Job.scheduled_at <= now,
                Job.is_deleted.is_(False),
                Tenant.is_deleted.is_(False),
            )
        )

        if self._last_tenant_id is not None:
            candidate = candidate.order_by(
                case(
                    (Tenant.id > self._last_tenant_id, 0),
                    else_=1,
                ),
                Tenant.id,
                Job.scheduled_at,
                Job.id,
            )
        else:
            candidate = candidate.order_by(
                Tenant.id,
                Job.scheduled_at,
                Job.id,
            )

        candidate = (
            candidate
            .with_for_update(of=Job, skip_locked=True)
            .limit(1)
            .scalar_subquery()
        )

        async with AsyncSessionLocal() as session:
            async with session.begin():
                statement = (
                    update(Job)
                    .where(
                        Job.id == candidate,
                        Job.status == JobStatus.PENDING,
                        Job.scheduled_at <= now,
                        Job.is_deleted.is_(False),
                    )
                    .values(
                        status=JobStatus.RUNNING,
                        locked_by=self.worker_id,
                        lease_expires_at=now + timedelta(
                            seconds=settings.JOB_LEASE_DURATION
                        ),
                        started_at=now,
                        completed_at=None,
                        last_error=None,
                    )
                    .returning(Job)
                )

                claimed_job = (
                    await session.scalars(statement)
                ).one_or_none()

            # Update the cursor.
            if claimed_job is not None:
                self._last_tenant_id = claimed_job.tenant_id

            return claimed_job
        
    async def execute_claimed_job(self, job: Job) -> None:
        stop_event = asyncio.Event()

        handler_task = asyncio.create_task(
            execute_handler(
                tenant_id=job.tenant_id,
                job_id=job.id,
                job_type=job.handler,
                payload=job.payload or {},
            )
        )
        heartbeat_task = asyncio.create_task(
            self.heartbeat(job.id, stop_event)
        )

        try:
            done, _ = await asyncio.wait(
                {handler_task, heartbeat_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            # The heartbeat ended before the handler.
            if heartbeat_task in done and not handler_task.done():
                handler_task.cancel()

                try:
                    await handler_task
                except asyncio.CancelledError:
                    pass

                return

            # The handler finished first.
            stop_event.set()
            heartbeat_ok = await heartbeat_task

            if not heartbeat_ok:
                return

            try:
                result = handler_task.result()
            except Exception as exc:
                logger.exception("Job %s failed", job.id)
                await self.retry_or_fail(job.id, str(exc), job.retry_count)
                return

            now = datetime.now(timezone.utc)

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    update_result = await session.execute(
                        update(Job)
                        .where(
                            Job.id == job.id,
                            Job.status == JobStatus.RUNNING,
                            Job.locked_by == self.worker_id,
                            Job.lease_expires_at > now,
                        )
                        .values(
                            status=JobStatus.COMPLETED,
                            result=result,
                            completed_at=now,
                            locked_by=None,
                            lease_expires_at=None,
                        )
                    )

                    if update_result.rowcount == 1:
                        logger.info("Job %s completed", job.id)
                    else:
                        logger.warning(
                            "Job %s could not be completed because "
                            "its lease is no longer valid",
                            job.id,
                        )

        finally:
            stop_event.set()

            # Stop the handler if it is still running.
            if not handler_task.done():
                handler_task.cancel()

            # Stop the heartbeat.
            if not heartbeat_task.done():
                heartbeat_task.cancel()

            await asyncio.gather(
                handler_task,
                heartbeat_task,
                return_exceptions=True,
            )
    
    async def run(self) -> None:
        active_tasks: set[asyncio.Task] = set()

        try:
            while True:
                active_tasks = {
                    task for task in active_tasks if not task.done()
                }

                await self.recover_expired_jobs()

                while len(active_tasks) < settings.MAX_WORKERS:
                    job = await self.claim_next_job()

                    if job is None:
                        break

                    task = asyncio.create_task(
                        self.execute_claimed_job(job)
                    )
                    active_tasks.add(task)

                if active_tasks:
                    await asyncio.wait(
                        active_tasks,
                        timeout=settings.POLL_INTERVAL,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                else:
                    await asyncio.sleep(settings.POLL_INTERVAL)

        except asyncio.CancelledError:
            logger.info("Scheduler shutting down")

            if active_tasks:
                _, pending = await asyncio.wait(
                    active_tasks,
                    timeout=30,
                )

                # Cancel jobs that haven't finished within 30 seconds.
                for task in pending:
                    task.cancel()

                await asyncio.gather(
                    *active_tasks,
                    return_exceptions=True,
                )

            logger.info("Scheduler shutdown complete")
            raise

    async def renew_lease(self, job_id) -> bool:
        now = datetime.now(timezone.utc)

        async with AsyncSessionLocal() as session:
            async with session.begin():
                result = await session.execute(
                    update(Job)
                    .where(
                        Job.id == job_id,
                        Job.status == JobStatus.RUNNING,
                        Job.locked_by == self.worker_id,
                        Job.lease_expires_at > now,
                    )
                    .values(
                        lease_expires_at=now
                        + timedelta(seconds=settings.JOB_LEASE_DURATION)
                    )
                )

                return result.rowcount == 1

    async def heartbeat(
        self,
        job_id,
        stop_event: asyncio.Event,
    ) -> bool:
        interval = settings.JOB_LEASE_DURATION / 3

        while not stop_event.is_set():
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=interval,
                )
            except asyncio.TimeoutError:
                try:
                    renewed = await self.renew_lease(job_id)
                except Exception:
                    logger.exception(
                        "Could not renew lease for job %s",
                        job_id,
                    )
                    return False

                if not renewed:
                    logger.warning(
                        "Lease lost for job %s",
                        job_id,
                    )
                    return False

        return True

    async def retry_or_fail(
        self,
        job_id: UUID,
        error: str,
        retry_count: int,
    ) -> None:
        now = datetime.now(timezone.utc)
        retry_delay = 2 ** (retry_count + 1)
        next_retry_at = now + timedelta(seconds=retry_delay)

        can_retry = Job.retry_count < settings.MAX_RETRIES

        statement = (
            update(Job)
            .where(
                Job.id == job_id,
                Job.status == JobStatus.RUNNING,
                Job.locked_by == self.worker_id,
                Job.lease_expires_at > now,
            )
            .values(
                status=cast(
                    case(
                        (can_retry, JobStatus.PENDING.value),
                        else_=JobStatus.FAILED.value,
                    ),
                    Job.__table__.c.status.type,
                ),
                retry_count=case(
                    (can_retry, Job.retry_count + 1),
                    else_=Job.retry_count,
                ),
                last_retried_at=case(
                    (can_retry, now),
                    else_=Job.last_retried_at,
                ),
                scheduled_at=case(
                    (can_retry, next_retry_at),
                    else_=Job.scheduled_at,
                ),
                last_error=error,
                locked_by=None,
                lease_expires_at=None,
            )
            .returning(Job.status, Job.retry_count)
        )

        async with AsyncSessionLocal() as session:
            async with session.begin():
                row = (await session.execute(statement)).one_or_none()

        if row is None:
            logger.warning(
                "Could not retry job %s: lease lost or job no longer owned",
                job_id,
            )
        elif row.status == JobStatus.PENDING:
            logger.info(
                "Job %s scheduled for retry in %s seconds",
                job_id,
                retry_delay,
            )
        else:
            logger.error("Job %s failed permanently: %s", job_id, error)


    async def recover_expired_jobs(self) -> None:
        now = datetime.now(timezone.utc)
        can_retry = Job.retry_count < settings.MAX_RETRIES

        expired_jobs = (
            select(Job.id)
            .where(
                Job.status == JobStatus.RUNNING,
                Job.lease_expires_at <= now,
                Job.is_deleted.is_(False),
            )
            .order_by(Job.lease_expires_at, Job.id)
            .with_for_update(skip_locked=True)
            .limit(settings.MAX_WORKERS)
        )

        statement = (
            update(Job)
            .where(Job.id.in_(expired_jobs))
            .values(
                status=cast(
                    case(
                        (can_retry, JobStatus.PENDING.value),
                        else_=JobStatus.FAILED.value,
                    ),
                    Job.__table__.c.status.type,
                ),
                retry_count=case(
                    (can_retry, Job.retry_count + 1),
                    else_=Job.retry_count,
                ),
                last_retried_at=case(
                    (can_retry, now),
                    else_=Job.last_retried_at,
                ),
                last_error="Job lease expired",
                locked_by=None,
                lease_expires_at=None,
            )
            .returning(Job.id, Job.status)
        )

        async with AsyncSessionLocal() as session:
            async with session.begin():
                recovered = (await session.execute(statement)).all()

        if recovered:
            logger.info("Recovered %s expired jobs", len(recovered))