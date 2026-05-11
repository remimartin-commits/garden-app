from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _sample_quote_payload() -> dict:
    return {
        "quote": {
            "customer_id": 1,
            "property_id": 1,
            "title": "Garden visit",
            "subtotal_ex_gst": 100.0,
            "gst_amount": 15.0,
            "total_inc_gst": 115.0,
        }
    }


def test_post_quote_then_get_by_id() -> None:
    created = client.post("/api/v1/quotes", json=_sample_quote_payload())
    assert created.status_code == 201
    qid = created.json()["quote"]["quote_id"]
    resp = client.get(f"/api/v1/quotes/{qid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["quote"]["quote_id"] == qid
    assert data["quote"]["title"] == "Garden visit"


def test_get_quote_not_found() -> None:
    assert client.get("/api/v1/quotes/99999").status_code == 404
