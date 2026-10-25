from uuid import UUID
from fastapi import status
from app.core.database import get_db
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.job.schemas import (
    JobResponse, JobCreatePayload,
    JobPayload
)
from app.api.job.service import (
    list_jobs, get_job,
    create_job, delete_job,
    update_job
)

router = APIRouter(prefix="/job", tags=["Jobs"])

@router.get("/", response_model=list[JobResponse])
async def list_jobs_controller(
    tenant_id: UUID | None = None, 
    session: AsyncSession = Depends(get_db),
):
    jobs = await list_jobs(
        session=session,
        tenant_id=tenant_id
    )

    return jobs

@router.get("/{job_id}", response_model=JobResponse)
async def get_job_controller(
    job_id: UUID, 
    session: AsyncSession = Depends(get_db),
):
    job = await get_job(
        session=session,
        job_id=job_id
    )

    return job


@router.post("/", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job_controller(
    payload: JobCreatePayload,
    session: AsyncSession = Depends(get_db),
):
    job = await create_job(
        session=session,
        create_payload=payload
    )

    return job


@router.put("/{job_id}", response_model=JobResponse)
async def update_job_controller(
    job_id: UUID, 
    payload: JobPayload,
    session: AsyncSession = Depends(get_db),
):
    job = await update_job(
        session=session,
        job_id=job_id,
        update_payload=payload
    )

    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job_controller(
    job_id: UUID, 
    session: AsyncSession = Depends(get_db),
):
    await delete_job(
        session=session,
        job_id=job_id,
    )


