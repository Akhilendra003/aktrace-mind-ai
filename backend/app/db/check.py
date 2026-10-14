"""Read-only database probe: python -m app.db.check (0=ready, 1=unavailable)."""

from pydantic import ValidationError
from pydantic_settings import SettingsError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import load_settings
from app.core.logging import configure_logging
from app.db.session import create_database_engine

logger = configure_logging()


def database_is_available(session: Session) -> bool:
    try:
        return session.execute(text("SELECT 1")).scalar_one() == 1
    except SQLAlchemyError:
        # Driver exceptions can contain hosts, users, and connection details.
        logger.warning("database_unavailable")
        return False


def main() -> int:
    try:
        settings = load_settings()
    except (ValidationError, SettingsError):
        logger.error("database_configuration_invalid")
        print("Database configuration invalid. Check backend/.env; no values were logged.")
        return 1

    engine = create_database_engine(settings)
    try:
        with Session(engine) as session:
            available = database_is_available(session)
        print(
            "Database connection successful." if available else "Database connection unavailable."
        )
        return 0 if available else 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
