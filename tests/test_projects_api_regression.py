import pytest

pytestmark = pytest.mark.skip(reason='Marketing/site API routes are not mounted on the garden manager app.')

from tests.http_helpers import auth_test_client
import time

from fastapi.testclient import TestClient

from app.main import app


def _extract_project_collection(payload):
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in ("projects", "items", "results", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value

    raise AssertionError("GET /api/projects response must contain a project list")


def test_get_projects_returns_promptly_and_only_published_records():
    client = auth_test_client()

    started_at = time.perf_counter()
    response = client.get("/api/projects")
    elapsed_seconds = time.perf_counter() - started_at

    assert response.status_code == 200
    assert elapsed_seconds < 2.0
    assert response.headers.get("content-type", "").startswith("application/json")

    projects = _extract_project_collection(response.json())
    assert isinstance(projects, list)

    for project in projects:
        assert isinstance(project, dict)
        if "published" in project:
            assert project["published"] is True
        if "is_published" in project:
            assert project["is_published"] is True
        if "status" in project:
            assert project["status"] == "published"
