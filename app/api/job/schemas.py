from uuid import UUID
from pydantic import BaseModel, ConfigDict
from datetime import datetime

from app.api.job.constants import JobStatus

class JobResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str | None
    description: str | None
    scheduled_at: datetime
    handler: str
    payload: dict
    status: JobStatus
    result: dict | None
    retry_count: int
    last_retried_at: datetime | None

    model_config = ConfigDict(from_attributes=True)



class JobPayload(BaseModel):
    name: str | None
    description: str | None
    scheduled_at: datetime
    handler: str
    payload: dict
    
    model_config = ConfigDict(from_attributes=True)

class JobCreatePayload(JobPayload):
    tenant_id: UUID
    
    model_config = ConfigDict(from_attributes=True)
