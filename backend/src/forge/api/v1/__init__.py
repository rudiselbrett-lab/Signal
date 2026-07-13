from fastapi import APIRouter

from forge.api.v1 import health

api_router = APIRouter()
api_router.include_router(health.router)
