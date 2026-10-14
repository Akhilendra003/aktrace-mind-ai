"""One engine per process; one short-lived session per request."""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import URL, Engine, create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings


def create_database_engine(settings: Settings) -> Engine:
    # URL.create safely handles @, :, / and other characters in passwords.
    url = URL.create(
        drivername="postgresql+psycopg",
        username=settings.db_user,
        password=settings.db_password.get_secret_value(),
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
    )
    return create_engine(
        url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=settings.db_pool_recycle,
        pool_pre_ping=True,
        echo=False,
        hide_parameters=True,
        connect_args={
            "connect_timeout": settings.db_connect_timeout,
            "sslmode": settings.db_sslmode,
            "options": f"-c statement_timeout={settings.db_statement_timeout_ms}",
            "application_name": "aktrace-mind-ai",
        },
    )


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        # Closing also rolls back unfinished work and returns the connection.
        # Commits must be explicit in future write operations.
