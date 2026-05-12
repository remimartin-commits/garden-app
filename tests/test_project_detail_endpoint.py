import pytest

pytestmark = pytest.mark.skip(reason='Marketing/site API routes are not mounted on the garden manager app.')

from tests.http_helpers import auth_test_client
from fastapi.testclient import TestClient

from app.main import app


client = auth_test_client()


def test_get_project_by_slug_returns_case_study():
    response = client.get("/api/projects/auckland-family-fibreglass-pool")

    assert response.status_code == 200
    data = response.json()
    assert "project" in data
    project = data["project"]
    assert project["slug"] == "auckland-family-fibreglass-pool"
    assert project["title"] == "Auckland Family Fibreglass Pool Installation"
    assert project["location"] == "Auckland"
    assert project["pool_type"] == "Fibreglass"
    assert "features" in project


def test_get_project_by_slug_returns_404_for_unknown_slug():
    response = client.get("/api/projects/not-a-real-project")

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"
