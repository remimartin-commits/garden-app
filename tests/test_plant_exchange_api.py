from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_and_list_wanted_plant() -> None:
    r = client.post(
        "/api/v1/plant-listings",
        json={"kind": "wanted", "plant_name": "Kawakawa", "quantity": "2", "notes": "Shade tolerant"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["kind"] == "wanted"
    assert data["plant_name"] == "Kawakawa"
    assert data["status"] == "open"
    lid = data["id"]
    listed = client.get("/api/v1/plant-listings?kind=wanted")
    assert listed.status_code == 200
    ids = [x["id"] for x in listed.json()["listings"]]
    assert lid in ids


def test_patch_giveaway_status() -> None:
    r = client.post(
        "/api/v1/plant-listings",
        json={"kind": "giveaway", "plant_name": "Agapanthus divisions", "notes": "Pickup weekends"},
    )
    assert r.status_code == 201
    lid = r.json()["id"]
    assert r.json()["status"] == "available"
    u = client.patch(f"/api/v1/plant-listings/{lid}", json={"status": "reserved"})
    assert u.status_code == 200
    assert u.json()["status"] == "reserved"
    assert u.json()["plant_name"] == "Agapanthus divisions"


def test_delete_plant_listing_404_when_missing() -> None:
    gone = client.delete("/api/v1/plant-listings/999999")
    assert gone.status_code == 404


def test_patch_plant_listing_404_when_missing() -> None:
    r = client.patch("/api/v1/plant-listings/999999", json={"plant_name": "X"})
    assert r.status_code == 404
