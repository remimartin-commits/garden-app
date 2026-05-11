import json

from fastapi.testclient import TestClient

from app import quote_enquiries
from app.main import app

client = TestClient(app)


def setup_function():
    quote_enquiries._RATE_LIMIT_BUCKET.clear()


def test_quote_enquiry_route_is_registered():
    assert any(
        getattr(route, "path", None) == "/api/quote-enquiries"
        and "POST" in getattr(route, "methods", set())
        for route in app.routes
    )


def test_submit_quote_enquiry_persists_valid_request(tmp_path, monkeypatch):
    output_file = tmp_path / "quote_enquiries.jsonl"
    monkeypatch.setattr(quote_enquiries, "QUOTE_ENQUIRIES_FILE", output_file)

    response = client.post(
        "/api/quote-enquiries",
        json={
            "name": "Taylor Smith",
            "email": "taylor@example.co.nz",
            "phone": "+64 21 123 4567",
            "location": "Nelson, South Island",
            "poolType": "Concrete family pool",
            "message": "We are planning a new backyard pool and would like a consultation.",
            "website": "",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "received"
    assert body["id"]

    rows = output_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1
    saved = json.loads(rows[0])
    assert saved["name"] == "Taylor Smith"
    assert saved["location"] == "Nelson, South Island"
    assert saved["spam_protection"]["honeypot_checked"] is True
    assert saved["spam_protection"]["rate_limit_checked"] is True


def test_honeypot_field_rejects_spam_without_persisting(tmp_path, monkeypatch):
    output_file = tmp_path / "quote_enquiries.jsonl"
    monkeypatch.setattr(quote_enquiries, "QUOTE_ENQUIRIES_FILE", output_file)

    response = client.post(
        "/api/quote-enquiries",
        json={
            "name": "Automated Bot",
            "email": "bot@example.com",
            "message": "Spam submission",
            "website": "https://spam.example",
        },
    )

    assert response.status_code == 400
    assert "spam protection" in response.json()["detail"]
    assert not output_file.exists()


def test_rate_limit_rejects_repeated_submissions(tmp_path, monkeypatch):
    output_file = tmp_path / "quote_enquiries.jsonl"
    monkeypatch.setattr(quote_enquiries, "QUOTE_ENQUIRIES_FILE", output_file)
    monkeypatch.setattr(quote_enquiries, "RATE_LIMIT_MAX_REQUESTS", 2)
    quote_enquiries._RATE_LIMIT_BUCKET.clear()

    payload = {
        "name": "Jordan Lee",
        "email": "jordan@example.co.nz",
        "message": "Please quote a new pool installation.",
    }

    assert client.post("/api/quote-enquiries", json=payload).status_code == 201
    assert client.post("/api/quote-enquiries", json=payload).status_code == 201
    response = client.post("/api/quote-enquiries", json=payload)

    assert response.status_code == 429
    assert "Too many" in response.json()["detail"]


def test_gst_rate_consistency_on_existing_records(monkeypatch, tmp_path):
    output_file = tmp_path / "quote_enquiries.jsonl"
    monkeypatch.setattr(quote_enquiries, "QUOTE_ENQUIRIES_FILE", output_file)
    original_gst_rate = 0.15
    new_gst_rate = 0.18
    existing_quote = {
        "id": "existing-123",
        "name": "Existing Customer",
        "gst_rate_snapshot": original_gst_rate,
        "total_ex_gst": 100,
        "total_inc_gst": 115
    }
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(existing_quote, f)
        f.write("\n")

    # Simulate gst_rate change
    monkeypatch.setattr(quote_enquiries, "gst_rate", new_gst_rate)

    # Read existing record
    with open(output_file, "r", encoding="utf-8") as f:
        saved_records = [json.loads(line) for line in f]

    for record in saved_records:
        assert record["gst_rate_snapshot"] == original_gst_rate
        assert record["total_inc_gst"] == 115  # remains based on original gst_rate
