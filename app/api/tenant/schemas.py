from uuid import UUID
from pydantic import BaseModel, ConfigDict

class TenantResponse(BaseModel):
    id: UUID
    name: str | None

    model_config = ConfigDict(from_attributes=True)

class TenantRequest(BaseModel):
    name: str | None

    model_config = ConfigDict(from_attributes=True)

