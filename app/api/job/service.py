from uuid import UUID
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import APIBaseException

from app.api.job.models import Job
from app.api.job.constants import JobStatus
from app.api.job.schemas import (
    JobResponse, 
    JobPayload, 
    JobCreatePayload
)

async def list_jobs(
    session: AsyncSession,
    tenant_id: UUID | None
) -> list[JobResponse]:
    stmt = select(Job).where(
        Job.not_deleted(),
    )

    if tenant_id:
        stmt = stmt.where(Job.tenant_id == tenant_id)

    result = await session.execute(stmt)
    jobs: list[Job] = result.scalars()

    return [JobResponse.model_validate(job) for job in jobs]


async def get_job(
    session: AsyncSession,
    job_id: UUID
) -> JobResponse:
    stmt = select(Job).where(
        Job.not_deleted(),
        Job.id == job_id
    )

    result = await session.execute(stmt)
    job: Job | None = result.scalar_one_or_none()

    if job is None:
        raise APIBaseException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    return JobResponse.model_validate(job)


async def create_job(
    session: AsyncSession,
    create_payload: JobCreatePayload
) -> JobResponse:
    job = Job(
        tenant_id = create_payload.tenant_id,
        name = create_payload.name,
        description = create_payload.description,
        scheduled_at = create_payload.scheduled_at,
        handler = create_payload.handler,
        payload = create_payload.payload
    ) 
    session.add(job)

    await session.commit()
    await session.refresh(job)

    return JobResponse.model_validate(job)


async def update_job(
    session: AsyncSession,
    job_id: UUID,
    update_payload: JobPayload
) -> JobResponse:
    stmt = select(Job).where(
        Job.not_deleted(),
        Job.id == job_id
    )

    result = await session.execute(stmt)
    job: Job | None = result.scalar_one_or_none()

    if job is None:
        raise APIBaseException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    if job.status != JobStatus.PENDING:
        raise APIBaseException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job is not pending"
        )

    job.name = update_payload.name
    job.description = update_payload.description
    job.scheduled_at = update_payload.scheduled_at
    job.payload = update_payload.payload
    job.handler = update_payload.handler

    await session.commit()
    await session.refresh(job)

    return JobResponse.model_validate(job)


async def delete_job(
    session: AsyncSession,
    job_id: UUID
):
    stmt = select(Job).where(
        Job.not_deleted(),
        Job.id == job_id
    )

    result = await session.execute(stmt)
    job: Job | None = result.scalar_one_or_none()

    if job is None:
        raise APIBaseException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    job.soft_delete()
    await session.commit()





    
