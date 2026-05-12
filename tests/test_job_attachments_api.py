from __future__ import annotations

import io

from tests.http_helpers import auth_test_client


def test_job_attachment_upload_returns_503_when_storage_not_configured(monkeypatch) -> None:
    # Do not depend on the developer machine's .env (S3 may be fully configured locally).
    monkeypatch.setattr("app.config.s3_job_attachments_configured", lambda: False)
    client = auth_test_client()
    files = {"file": ("test.jpg", io.BytesIO(b"fake-bytes-not-a-jpeg"), "image/jpeg")}
    r = client.post("/api/v1/jobs/1/attachments", files=files)
    assert r.status_code == 503
    assert "not configured" in r.json().get("detail", "").lower()
