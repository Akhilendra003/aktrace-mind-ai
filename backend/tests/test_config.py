"""Settings validation, precedence, and secret-safe representations."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import ENV_FILE, Settings


def test_env_file_path_is_independent_of_working_directory() -> None:
    assert ENV_FILE == Path(__file__).resolve().parents[1] / ".env"


def test_environment_overrides_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("DB_PORT=5433\nDB_POOL_SIZE=3\nUNRELATED_SETTING=ok\n", encoding="utf-8")
    monkeypatch.setenv("DB_PORT", "5434")
    settings = Settings(_env_file=env_file)
    assert settings.db_port == 5434
    assert settings.db_pool_size == 3


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("DB_PORT", "0"),
        ("DB_PORT", "65536"),
        ("DB_PORT", "not-a-port"),
        ("DB_POOL_SIZE", "0"),
        ("DB_MAX_OVERFLOW", "-1"),
        ("DB_POOL_TIMEOUT", "0"),
        ("DB_CONNECT_TIMEOUT", "0"),
        ("DB_STATEMENT_TIMEOUT_MS", "0"),
        ("DB_SSLMODE", "invalid"),
        ("DB_PASSWORD", ""),
    ],
)
def test_invalid_settings_rejected(field: str, value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(field, value)
    with pytest.raises(ValidationError):
        Settings()


def test_missing_credentials_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DB_PASSWORD")
    with pytest.raises(ValidationError):
        Settings()


def test_password_masked() -> None:
    settings = Settings()
    assert settings.db_password.get_secret_value() not in repr(settings)
    assert settings.db_password.get_secret_value() not in settings.model_dump_json()


def test_validation_errors_do_not_display_input(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_PORT", "private-invalid-value")
    with pytest.raises(ValidationError) as error:
        Settings()
    assert "private-invalid-value" not in str(error.value)
