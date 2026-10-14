"""Provision only missing resources; preserve existing database ownership/passwords."""

from unittest.mock import MagicMock

import pytest

from app.core.config import Settings
from app.db import setup


def test_provisions_missing_role_and_database(monkeypatch: pytest.MonkeyPatch) -> None:
    connect = MagicMock()
    connection = connect.return_value.__enter__.return_value
    missing = MagicMock()
    missing.fetchone.return_value = None
    connection.execute.return_value = missing
    monkeypatch.setattr(setup.psycopg, "connect", connect)
    setup.provision_database(Settings(), "test-admin", "test-admin-password")
    queries = [call.args[0] for call in connection.execute.call_args_list]
    assert len(queries) == 4
    assert "NOSUPERUSER NOCREATEDB NOCREATEROLE" in queries[1].as_string()
    assert 'CREATE DATABASE "unit_test_database" OWNER "unit_test_user"' == queries[3].as_string()
    assert connect.call_args.kwargs["autocommit"] is True


def test_existing_resources_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    connect = MagicMock()
    connection = connect.return_value.__enter__.return_value
    connection.execute.return_value.fetchone.side_effect = [(1,), ("unit_test_user",)]
    monkeypatch.setattr(setup.psycopg, "connect", connect)
    setup.provision_database(Settings(), "test-admin", "test-admin-password")
    assert connection.execute.call_count == 2
    assert all(call.args[0].startswith("SELECT") for call in connection.execute.call_args_list)


def test_existing_owner_is_not_changed(monkeypatch: pytest.MonkeyPatch) -> None:
    connect = MagicMock()
    connection = connect.return_value.__enter__.return_value
    connection.execute.return_value.fetchone.side_effect = [(1,), ("another_owner",)]
    monkeypatch.setattr(setup.psycopg, "connect", connect)
    with pytest.raises(RuntimeError, match="different owner"):
        setup.provision_database(Settings(), "test-admin", "test-admin-password")
    assert connection.execute.call_count == 2
