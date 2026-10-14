"""Verify the public Phase 1 API contract."""

import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.logging import JsonFormatter
from app.main import app, handle_unexpected_error
from main import app as legacy_app


def test_application_import() -> None:
    assert isinstance(app, FastAPI)
    assert legacy_app is app


@pytest.mark.parametrize(
    ("path", "payload"),
    [("/", {"message": "AkTrace Mind AI is running"}), ("/health", {"status": "healthy"})],
)
def test_endpoints(path: str, payload: dict[str, str]) -> None:
    with TestClient(app) as client:
        response = client.get(path)
    assert response.status_code == 200
    assert response.json() == payload
    assert response.headers["content-type"] == "application/json"


def test_swagger_and_openapi() -> None:
    with TestClient(app) as client:
        docs = client.get("/docs")
        schema = client.get("/openapi.json")
    assert docs.status_code == 200
    assert "swagger-ui" in docs.text
    assert schema.status_code == 200
    assert schema.json()["info"] == {"title": "AkTrace Mind AI", "version": "1.0.0"}
    assert {"/", "/health"} <= schema.json()["paths"].keys()


def test_http_errors() -> None:
    with TestClient(app) as client:
        assert client.get("/missing").status_code == 404
        assert client.post("/health").status_code == 405


def test_unexpected_error_is_sanitized() -> None:
    def broken_health() -> None:
        raise RuntimeError("private internal details")

    # A separate app keeps the production routes unchanged.
    failing_app = FastAPI()
    failing_app.add_exception_handler(Exception, handle_unexpected_error)
    failing_app.get("/health")(broken_health)
    with TestClient(failing_app, raise_server_exceptions=False) as client:
        response = client.get("/health")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}


def test_structured_logging() -> None:
    record = logging.LogRecord("aktrace", logging.INFO, __file__, 1, "request_completed", (), None)
    record.status_code = 200
    entry = json.loads(JsonFormatter().format(record))
    assert entry["message"] == "request_completed"
    assert entry["status_code"] == 200
    assert entry["level"] == "INFO"
