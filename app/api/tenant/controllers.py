from uuid import UUID
from fastapi import status

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from app.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tenant.schemas import (
    TenantResponse, TenantRequest
)
from app.api.tenant.service import (
    list_tenants,
    get_tenant,
    create_tenant,
    update_tenant,
    delete_tenant
)

router = APIRouter(prefix="/tenant", tags=["Tenants"])

@router.get("/", response_model=list[TenantResponse])
async def list_tenants_controller(
    session: AsyncSession = Depends(get_db)
):
    tenants = await list_tenants(session=session)

    return tenants
    

@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenants_controller(
    tenant_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    tenant = await get_tenant(session=session, tenant_id=tenant_id)

    return tenant

@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant_controller(
    payload: TenantRequest,
    session: AsyncSession = Depends(get_db),
):
    tenant = await create_tenant(session=session, payload=payload)

    return tenant


@router.put("/{tenant_id}", response_model=TenantResponse)
async def update_tenant_controller(
    tenant_id: UUID,
    payload: TenantRequest,
    session: AsyncSession = Depends(get_db),
):
    tenant = await update_tenant(session=session, tenant_id=tenant_id, payload=payload)
    return tenant



@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant_controller(
    tenant_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    await delete_tenant(session=session, tenant_id=tenant_id)



