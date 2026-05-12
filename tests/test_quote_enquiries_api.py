import pytest

pytestmark = pytest.mark.skip(reason='Marketing/site API routes are not mounted on the garden manager app.')

from tests.http_helpers import auth_test_client
import json
from fastapi.testclient import TestClient
from app.main import app
from app import quote_enquiries

def test_post_quote_enquiry_persists_valid_request(tmp_path, monkeypatch):
    log_path = tmp_path / "quote_enquiries.jsonl"
    monkeypatch.setattr(quote_enquiries, "QUOTE_ENQUIRIES_FILE", log_path)

    client = auth_test_client()
    response = client.post(
        "/api/quote-enquiries",
        json={
            "name": "Aroha Smith",
            "email": "aroha@example.co.nz",
            "phone": "021 555 0101",
            "location": "Tauranga, Bay of Plenty",
            "client_type": "homeowner",
            "pool_type": "fibreglass family pool",
            "timeline": "This summer",
            "message": "We would like a consultation and quote for a new pool installation.",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "received"
    assert body["id"]
    assert log_path.exists()

    saved = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert saved["id"] == body["id"]
    assert saved["name"] == "Aroha Smith"
    assert saved["location"] == "Tauranga, Bay of Plenty"
    assert saved["status"] == "new"


def test_post_quote_enquiry_rejects_missing_contact_details(tmp_path, monkeypatch):
    log_path = tmp_path / "quote_enquiries.jsonl"
    monkeypatch.setattr(quote_enquiries, "QUOTE_ENQUIRIES_FILE", log_path)

    client = auth_test_client()
    response = client.post(
        "/api/quote-enquiries",
        json={
            "name": "No Contact",
            "location": "Christchurch",
            "message": "Please quote a pool.",
        },
    )

    assert response.status_code == 400
    assert "email or phone is required" in response.text
    assert not log_path.exists()
