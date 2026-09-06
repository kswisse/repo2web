from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.api.v1.router import api_router

settings = get_settings()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting Repo2Web API", env=settings.APP_ENV)
    yield
    logger.info("Shutting down Repo2Web API")


def create_app() -> FastAPI:
    application = FastAPI(
        title="Repo2Web API",
        description="Convert GitHub repositories into runnable web applications",
        version="0.1.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.error_code,
                    "detail": exc.detail,
                }
            },
            headers=exc.headers,
        )

    application.include_router(api_router, prefix="/api/v1")

    return application


app = create_app()
