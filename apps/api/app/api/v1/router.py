from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.repositories import router as repositories_router
from app.api.v1.deployments import router as deployments_router

api_router = APIRouter()

api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(repositories_router, prefix="/repositories", tags=["repositories"])
api_router.include_router(deployments_router, prefix="/deployments", tags=["deployments"])
