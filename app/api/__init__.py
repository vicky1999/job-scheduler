from fastapi import APIRouter
from app.api.tenant.controllers import router as tenant_router
from app.api.job.controllers import router as job_router


api_router = APIRouter(prefix="/api")

api_router.include_router(tenant_router)
api_router.include_router(job_router)
