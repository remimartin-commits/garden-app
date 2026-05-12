from __future__ import annotations

from tests.http_helpers import auth_test_client

from fastapi.testclient import TestClient

from app.main import app

client = auth_test_client()


def test_patch_quote_updates_title() -> None:
    created = client.post(
        "/api/v1/quotes",
        json={
            "quote": {
                "customer_id": 1,
                "property_id": 1,
                "title": "Before",
                "subtotal_ex_gst": 100.0,
                "gst_amount": 15.0,
                "total_inc_gst": 115.0,
            }
        },
    )
    assert created.status_code == 201
    qid = created.json()["quote"]["quote_id"]
    r = client.patch(f"/api/v1/quotes/{qid}", json={"title": "After patch"})
    assert r.status_code == 200
    assert r.json()["quote"]["title"] == "After patch"
