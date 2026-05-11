from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_get_project_by_slug_returns_case_study():
    response = client.get("/api/projects/auckland-family-fibreglass-pool")

    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == "auckland-family-fibreglass-pool"
    assert data["title"] == "Auckland Family Fibreglass Pool Installation"
    assert data["location"] == "Auckland"
    assert data["island"] == "North Island"
    assert data["poolType"] == "Fibreglass in-ground pool"
    assert data["clientType"] == "Homeowner"
    assert data["images"]
    assert data["features"]
    assert "Pool design" in data["services"]
    assert data["cta"]["href"] == "/contact#quote"


def test_get_project_by_slug_supports_trailing_slash():
    response = client.get("/api/projects/queenstown-luxury-concrete-pool/")

    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == "queenstown-luxury-concrete-pool"
    assert data["region"] == "Otago"
    assert data["island"] == "South Island"


def test_get_project_by_slug_returns_404_for_unknown_project():
    response = client.get("/api/projects/not-a-real-project")

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}
