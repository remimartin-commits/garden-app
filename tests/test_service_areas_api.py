import pytest

pytestmark = pytest.mark.skip(reason='Marketing/site API routes are not mounted on the garden manager app.')

from tests.http_helpers import auth_test_client
from fastapi.testclient import TestClient

from app.main import app


client = auth_test_client()


def test_get_service_areas_returns_nationwide_pool_installation_coverage():
    response = client.get("/api/service-areas")

    assert response.status_code == 200
    payload = response.json()

    assert payload["coverage"]["country"] == "New Zealand"
    assert payload["coverage"]["nationwide"] is True
    assert set(payload["coverage"]["islands"]) == {"North Island", "South Island"}

    service_areas = payload["service_areas"]
    assert isinstance(service_areas, list)
    assert len(service_areas) >= 10

    names = {area["name"] for area in service_areas}
    assert "Auckland" in names
    assert "Wellington Region" in names
    assert "Canterbury" in names
    assert "Otago" in names

    islands = {area["island"] for area in service_areas}
    assert "North Island" in islands
    assert "South Island" in islands


def test_get_service_areas_items_include_required_lead_generation_fields():
    response = client.get("/api/service-areas")

    assert response.status_code == 200
    service_areas = response.json()["service_areas"]

    for area in service_areas:
        assert area["slug"]
        assert area["name"]
        assert area["island"] in {"North Island", "South Island"}
        assert area["available"] is True
        assert "pool" in area["summary"].lower()
        assert isinstance(area["key_locations"], list)
        assert area["key_locations"]
