from fastapi import APIRouter

from forge.api.v1 import articles, discovery, health, search, sources

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(sources.router)
api_router.include_router(sources.categories_router)
api_router.include_router(discovery.router)
api_router.include_router(articles.router)
api_router.include_router(search.router)
