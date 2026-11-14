from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.router import api_router
from app.core.config import settings
from app.database.session import engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and clean database pool shutdown."""
    logger.info(
        "Starting %s API (environment=%s)",
        settings.APP_NAME,
        settings.APP_ENV,
    )
    try:
        yield
    finally:
        engine.dispose()
        logger.info("Shutting down %s API", settings.APP_NAME)


app = FastAPI(
    title=f"{settings.APP_NAME} API",
    description="AI-powered CCTV monitoring and analytics platform",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# Configurable CORS access for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(SQLAlchemyError)
def sqlalchemy_exception_handler(
    request: Request,
    exc: SQLAlchemyError,
) -> JSONResponse:
    """Return a safe 500 response for unhandled database errors without leaking details."""
    logger.error(
        "Unhandled database error on %s %s: %s",
        request.method,
        request.url.path,
        type(exc).__name__,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "A database error occurred."},
    )


@app.get("/")
def root():
    return {
        "message": f"{settings.APP_NAME} API is running",
        "status": "online",
        "environment": settings.APP_ENV,
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "application": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "version": settings.APP_VERSION,
    }


@app.get("/health/database")
def database_health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "connected",
            "database": "PostgreSQL",
            "message": "Database connection successful",
        }

    except SQLAlchemyError:
        logger.warning("Database health check failed")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "disconnected",
                "database": "PostgreSQL",
                "message": "Database connection failed",
            },
        )


if api_router.routes:
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
