"""Content-type normalization for job photo uploads (JPEG edge cases)."""

from __future__ import annotations

from app.s3_uploads import _normalize_image_content_type


def test_image_jpg_maps_to_jpeg() -> None:
    assert _normalize_image_content_type("image/jpg", "x.jpg") == "image/jpeg"


def test_octet_stream_with_jpg_extension() -> None:
    assert _normalize_image_content_type("application/octet-stream", "IMG_0001.JPG") == "image/jpeg"


def test_missing_ct_with_jpeg_extension() -> None:
    assert _normalize_image_content_type(None, "folder/photo.jpeg") == "image/jpeg"


def test_standard_jpeg_unchanged() -> None:
    assert _normalize_image_content_type("image/jpeg", "a.bin") == "image/jpeg"
