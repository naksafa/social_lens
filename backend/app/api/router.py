from fastapi import APIRouter

from app.api.routes import ai, analytics, demo, files, health, projects, report

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(projects.router)
api_router.include_router(files.router)
api_router.include_router(files.meta_router)
api_router.include_router(analytics.router)
api_router.include_router(ai.router)
api_router.include_router(report.router)
api_router.include_router(demo.router)
