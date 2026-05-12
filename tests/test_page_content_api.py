import pytest

pytestmark = pytest.mark.skip(reason='Marketing/site API routes are not mounted on the garden manager app.')

from tests.http_helpers import auth_test_client
from fastapi.testclient import TestClient

from app.main import app

client = auth_test_client()


def test_get_published_home_page_by_slug():
    response = client.get("/api/pages/home")

    assert response.status_code == 200
    payload = response.json()
    assert payload["slug"] == "home"
    assert payload["status"] == "published"
    assert payload["title"] == "Nationwide Swimming Pool Design & Installation in New Zealand"
    assert payload["hero"]["heading"]
    assert any(section["id"] == "trust" for section in payload["sections"])


def test_get_services_page_includes_installation_process():
    response = client.get("/api/pages/services")

    assert response.status_code == 200
    payload = response.json()
    process_section = next(section for section in payload["sections"] if section["id"] == "installation-process")
    step_titles = [step["title"] for step in process_section["steps"]]
    assert step_titles == [
        "Consultation",
        "Design and planning",
        "Excavation and construction",
        "Finishing",
        "Handover",
    ]


def test_get_page_normalises_slug_case_and_slashes():
    response = client.get("/api/pages/COVERAGE/")

    assert response.status_code == 200
    assert response.json()["slug"] == "coverage"


def test_get_page_returns_404_for_unknown_slug():
    response = client.get("/api/pages/unknown-page")

    assert response.status_code == 404
    assert response.json()["detail"] == "Published page not found"


def test_get_page_returns_404_for_unpublished_page():
    response = client.get("/api/pages/draft-pricing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Published page not found"
