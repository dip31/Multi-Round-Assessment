"""
Aggregated API v1 router.

Imports all sub-routers from their respective module folders and exposes
a single ``api_router`` that ``main.py`` includes with one call.
"""

from fastapi import APIRouter

from app.modules.aptitude.routers.aptitude_router import router as aptitude_router
from app.modules.auth.routers.auth_router import router as auth_router
from app.modules.coding.routers.coding_router import router as coding_router
from app.modules.proctoring.routers.proctoring_router import router as proctoring_router
from app.modules.session.routers.session_router import router as session_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(session_router)
api_router.include_router(aptitude_router)
api_router.include_router(coding_router)
api_router.include_router(proctoring_router)
