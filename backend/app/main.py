from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.error_handlers import register_error_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware
from app.schemas.common import ErrorResponse

settings = get_settings()
configure_logging(settings.log_level, settings.log_json)
logger = get_logger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info(
        "app.startup",
        extra={
            "environment": settings.environment,
            "ai_provider": settings.ai_provider,
            "ai_configured": settings.ai_configured,
        },
    )
    yield
    logger.info("app.shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Multi-platform social media audit & marketing strategy engine. "
            "Deterministic analytics first, AI interpretation second."
        ),
        lifespan=lifespan,
        responses={500: {"model": ErrorResponse}},
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
