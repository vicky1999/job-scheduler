from uuid import UUID
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.exceptions import APIBaseException

from app.api.tenant.models import Tenant
from app.api.tenant.schemas import TenantRequest, TenantResponse

async def list_tenants(session: AsyncSession) -> list[TenantResponse]:
    stmt = select(Tenant).where(Tenant.not_deleted())

    result = await session.execute(stmt)
    tenants: list[Tenant] = result.scalars()
    return [TenantResponse.model_validate(tenant) for tenant in tenants]


async def get_tenant(session: AsyncSession, tenant_id: UUID) -> TenantResponse:
    stmt = select(Tenant).where(
        Tenant.not_deleted(),
        Tenant.id == tenant_id
    )

    result = await session.execute(stmt)
    tenant: Tenant | None = result.scalar_one_or_none()
    if tenant is None:
        raise APIBaseException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    return TenantResponse.model_validate(tenant)


async def create_tenant(session: AsyncSession, payload: TenantRequest) -> TenantResponse:
    tenant = Tenant(name=payload.name)
    session.add(tenant)

    await session.commit()
    await session.refresh(tenant)

    return TenantResponse.model_validate(tenant)


async def update_tenant(session: AsyncSession, tenant_id: UUID, payload: TenantRequest) -> TenantResponse:
    stmt = select(Tenant).where(
        Tenant.not_deleted(),
        Tenant.id == tenant_id
    )
    
    result = await session.execute(stmt)
    tenant: Tenant | None = result.scalar_one_or_none()

    if tenant is None:
        raise APIBaseException(
            detail = "Tenant not found"
        )

    tenant.name = payload.name
    await session.commit()

    return TenantResponse.model_validate(tenant)


async def delete_tenant(session: AsyncSession, tenant_id: UUID):
    stmt = select(Tenant).where(
        Tenant.not_deleted(),
        Tenant.id == tenant_id
    )
    
    result = await session.execute(stmt)
    tenant: Tenant | None = result.scalar_one_or_none()

    if tenant is None:
        raise APIBaseException(
            detail = "Tenant not found"
        )

    tenant.soft_delete()

    await session.commit()




