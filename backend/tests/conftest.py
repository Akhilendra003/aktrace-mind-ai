"""Keep unit tests independent of local secrets and PostgreSQL availability."""

import pytest

from app.core.config import Settings


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    if request.node.get_closest_marker("integration"):
        return
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
        monkeypatch.delenv(name.lower(), raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setenv("DB_NAME", "unit_test_database")
    monkeypatch.setenv("DB_USER", "unit_test_user")
    monkeypatch.setenv("DB_PASSWORD", "unit-test-placeholder")
