"""Swimming pool marketing site: static pages, catalog, projects, areas, quotes."""

from __future__ import annotations

from fastapi import APIRouter

from app.pool.areas import router as areas_router
from app.pool.catalog import router as catalog_router
from app.pool.pages import router as pages_router
from app.pool.projects import router as projects_router
from app.pool.quote_enquiries import router as quote_router

pool_router = APIRouter(tags=["pool"])
pool_router.include_router(pages_router)
pool_router.include_router(catalog_router)
pool_router.include_router(projects_router)
pool_router.include_router(areas_router)
pool_router.include_router(quote_router)

__all__ = ["pool_router"]
