from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.s3_uploads import delete_stored_attachment_object


def test_delete_stored_attachment_object_calls_delete_object(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.s3_job_attachments_configured", lambda: True)
    monkeypatch.setattr("app.config.S3_PUBLIC_BASE_URL", "https://pub.example", raising=False)
    monkeypatch.setattr("app.config.S3_BUCKET_NAME", "my-bucket", raising=False)
    monkeypatch.setattr("app.config.S3_JOBS_PREFIX", "job-attachments", raising=False)
    mock_client = MagicMock()
    monkeypatch.setattr("app.s3_uploads._s3_client", lambda: mock_client)
    delete_stored_attachment_object("https://pub.example/job-attachments/jobs/12/deadbeef_photo.jpg")
    mock_client.delete_object.assert_called_once_with(
        Bucket="my-bucket",
        Key="job-attachments/jobs/12/deadbeef_photo.jpg",
    )


def test_delete_stored_attachment_object_skips_non_managed_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.s3_job_attachments_configured", lambda: True)
    monkeypatch.setattr("app.config.S3_PUBLIC_BASE_URL", "https://pub.example", raising=False)
    monkeypatch.setattr("app.config.S3_JOBS_PREFIX", "job-attachments", raising=False)
    mock_client = MagicMock()
    monkeypatch.setattr("app.s3_uploads._s3_client", lambda: mock_client)
    delete_stored_attachment_object("https://pub.example/job-attachments/other/deadbeef.jpg")
    mock_client.delete_object.assert_not_called()
