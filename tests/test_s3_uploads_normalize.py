"""Content-type normalization for job photo uploads (JPEG edge cases)."""

from __future__ import annotations

import pytest

from app.s3_uploads import _normalize_image_content_type, attachment_object_key_from_file_url


def test_image_jpg_maps_to_jpeg() -> None:
    assert _normalize_image_content_type("image/jpg", "x.jpg") == "image/jpeg"


def test_octet_stream_with_jpg_extension() -> None:
    assert _normalize_image_content_type("application/octet-stream", "IMG_0001.JPG") == "image/jpeg"


def test_missing_ct_with_jpeg_extension() -> None:
    assert _normalize_image_content_type(None, "folder/photo.jpeg") == "image/jpeg"


def test_standard_jpeg_unchanged() -> None:
    assert _normalize_image_content_type("image/jpeg", "a.bin") == "image/jpeg"


def test_attachment_object_key_from_public_base(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.S3_PUBLIC_BASE_URL", "https://cdn.example", raising=False)
    monkeypatch.setattr("app.config.S3_JOBS_PREFIX", "job-attachments", raising=False)
    u = "https://cdn.example/job-attachments/jobs/99/aa_bb.jpg"
    assert attachment_object_key_from_file_url(u) == "job-attachments/jobs/99/aa_bb.jpg"


def test_attachment_object_key_suffix_without_matching_base(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.S3_PUBLIC_BASE_URL", "https://other.example", raising=False)
    monkeypatch.setattr("app.config.S3_JOBS_PREFIX", "job-attachments", raising=False)
    u = "https://cdn.example/job-attachments/recurring/3/x.png"
    assert attachment_object_key_from_file_url(u) == "job-attachments/recurring/3/x.png"
