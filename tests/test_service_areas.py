import pytest

pytestmark = pytest.mark.skip(reason='Marketing/site API routes are not mounted on the garden manager app.')

from tests.http_helpers import auth_test_client
from fastapi.testclient import TestClient

from app.entities import DashboardMetrics
from app.main import app


def test_service_area_content_confirms_nationwide_new_zealand_coverage():
    client = auth_test_client()

    response = client.get("/api/service-areas")

    assert response.status_code == 200
    payload = response.json()
    combined = " ".join(
        [
            payload["headline"],
            payload["summary"],
            payload["service_note"],
            " ".join(region["island"] for region in payload["regions"]),
            " ".join(location for region in payload["regions"] for location in region["locations"]),
        ]
    )
    assert "New Zealand" in combined
    assert "North Island" in combined
    assert "South Island" in combined
    assert "Auckland" in combined
    assert "Christchurch" in combined
