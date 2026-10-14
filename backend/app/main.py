"""FastAPI application composition and request logging."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from pydantic_settings import SettingsError
from sqlalchemy.orm import sessionmaker
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from app.api.health import router
from app.core.config import load_settings
from app.core.logging import configure_logging
from app.db.session import create_database_engine

logger = configure_logging()


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    try:
        settings = load_settings()
    except (ValidationError, SettingsError):
        raise RuntimeError("Invalid backend configuration. Check environment settings.") from None
    engine = create_database_engine(settings)
    application.state.session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(title="AkTrace Mind AI", version="1.0.0", lifespan=lifespan)
app.include_router(router)


@app.middleware("http")
async def log_request(request: Request, call_next: RequestResponseEndpoint) -> Response:
    started = perf_counter()
    response = await call_next(request)
    logger.info(
        "request_completed",
        extra={
            "method": request.method,
            "status_code": response.status_code,
            "duration_ms": round((perf_counter() - started) * 1000, 2),
        },
    )
    return response


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    # Do not expose exception messages, which may contain sensitive values.
    logger.error("request_failed", extra={"method": request.method, "status_code": 500})
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
