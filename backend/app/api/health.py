"""Basic service identity and liveness endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.check import database_is_available
from app.db.session import get_session

router = APIRouter(tags=["Health"])


@router.get("/")
def home() -> dict[str, str]:
    return {"message": "AkTrace Mind AI is running"}


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@router.get("/health/db", responses={503: {"description": "Database unavailable"}})
def database_health(session: Annotated[Session, Depends(get_session)]) -> dict[str, str]:
    if not database_is_available(session):
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "healthy", "database": "connected"}
