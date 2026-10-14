"""Database contracts with mocks; real connectivity requires explicit opt-in."""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError, TimeoutError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db import check
from app.db.session import create_database_engine, get_session
from app.main import app


def test_engine_configuration_and_lazy_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    import psycopg

    connect = MagicMock(side_effect=AssertionError("Engine creation must not connect"))
    monkeypatch.setattr(psycopg, "connect", connect)
    settings = Settings(db_password="special@:/?#password")
    engine = create_database_engine(settings)
    try:
        assert engine.url.drivername == "postgresql+psycopg"
        assert engine.url.password == "special@:/?#password"
        assert "special@:/?#password" not in str(engine.url)
        assert engine.pool.size() == 5
        assert engine.pool.timeout() == 5
        assert engine.pool._max_overflow == 5
        assert engine.pool._pre_ping is True
        assert engine.pool._recycle == 1800
        assert engine.hide_parameters is True
        assert engine.echo is False
        connect.assert_not_called()
    finally:
        engine.dispose()


def test_connection_timeout_and_ssl_are_passed_to_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    import psycopg

    connect = MagicMock(side_effect=psycopg.OperationalError("simulated connection failure"))
    monkeypatch.setattr(psycopg, "connect", connect)
    engine = create_database_engine(Settings(db_sslmode="require", db_connect_timeout=3))
    try:
        with pytest.raises(OperationalError):
            engine.connect()
        assert connect.call_args.kwargs["connect_timeout"] == 3
        assert connect.call_args.kwargs["sslmode"] == "require"
        assert connect.call_args.kwargs["options"] == "-c statement_timeout=5000"
    finally:
        engine.dispose()


@pytest.mark.parametrize("fail", [False, True])
def test_session_cleanup_and_rollback(fail: bool) -> None:
    factory = MagicMock()
    session = factory.return_value.__enter__.return_value
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(session_factory=factory)))
    dependency = get_session(request)
    assert next(dependency) is session
    if fail:
        with pytest.raises(ValueError):
            dependency.throw(ValueError("route failed"))
        session.rollback.assert_called_once()
    else:
        with pytest.raises(StopIteration):
            next(dependency)
    factory.return_value.__exit__.assert_called_once()
    session.commit.assert_not_called()


@pytest.mark.parametrize("failure", [None, "connection", "pool"])
def test_database_endpoint(failure: str | None, monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock()
    session.execute.return_value.scalar_one.return_value = 1
    if failure == "connection":
        session.execute.side_effect = OperationalError(
            "SELECT 1", {}, Exception("private-password")
        )
    elif failure == "pool":
        session.execute.side_effect = TimeoutError("private-password")
    warning = MagicMock()
    monkeypatch.setattr(check.logger, "warning", warning)
    app.dependency_overrides[get_session] = lambda: session
    try:
        with TestClient(app) as client:
            response = client.get("/health/db")
            assert client.get("/health").json() == {"status": "healthy"}
        assert response.status_code == (503 if failure else 200)
        assert response.json() == (
            {"detail": "Database unavailable"}
            if failure
            else {"status": "healthy", "database": "connected"}
        )
        assert "private-password" not in response.text
        assert "private-password" not in str(warning.call_args_list)
        assert str(session.execute.call_args.args[0]) == "SELECT 1"
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_lifespan_disposes_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as main_module

    engine = MagicMock()
    monkeypatch.setattr(main_module, "create_database_engine", lambda settings: engine)
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        engine.dispose.assert_not_called()
    engine.dispose.assert_called_once()


@pytest.mark.parametrize("available", [True, False])
def test_cli_exit_status_and_cleanup(
    available: bool, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    engine = MagicMock()
    monkeypatch.setattr(check, "create_database_engine", lambda settings: engine)
    monkeypatch.setattr(check, "Session", MagicMock())
    monkeypatch.setattr(check, "database_is_available", lambda session: available)
    assert check.main() == (0 if available else 1)
    engine.dispose.assert_called_once()
    assert "unit-test-placeholder" not in capsys.readouterr().out


def test_cli_invalid_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_PORT", "invalid")
    assert check.main() == 1


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("RUN_DATABASE_TESTS") != "1", reason="Set RUN_DATABASE_TESTS=1")
def test_real_postgresql_connection() -> None:
    engine = create_database_engine(Settings())
    try:
        with Session(engine) as session:
            assert check.database_is_available(session), (
                "Configured PostgreSQL connection unavailable"
            )
    finally:
        engine.dispose()
