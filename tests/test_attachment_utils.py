from __future__ import annotations

from app.attachment_utils import (
    attachment_file_urls_removed,
    coerce_attachments_list,
    safe_image_filename,
)


def test_coerce_attachments_list_filters_invalid() -> None:
    assert coerce_attachments_list(None) == []
    assert coerce_attachments_list([{"filename": "a.jpg", "file_url": "https://x/a"}]) == [
        {"filename": "a.jpg", "file_url": "https://x/a"}
    ]
    assert coerce_attachments_list([{"filename": "", "file_url": "https://x"}]) == []


def test_coerce_strips_presigned_s3_query_string() -> None:
    signed = (
        "https://pub.example/job-attachments/jobs/1/abc_photo.jpg"
        "?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Signature=deadbeef"
    )
    got = coerce_attachments_list([{"filename": "photo.jpg", "file_url": signed}])
    assert got == [{"filename": "photo.jpg", "file_url": "https://pub.example/job-attachments/jobs/1/abc_photo.jpg"}]


def test_safe_image_filename() -> None:
    assert safe_image_filename("weird name!!.jpeg", "png").endswith(".jpg")
    assert safe_image_filename("noext", "png").endswith(".png")


def test_attachment_file_urls_removed() -> None:
    before = [
        {"filename": "a.jpg", "file_url": "https://x/a.jpg"},
        {"filename": "b.jpg", "file_url": "https://x/b.jpg?X-Amz-Signature=1&X-Amz-Algorithm=AWS4"},
    ]
    after = [{"filename": "a.jpg", "file_url": "https://x/a.jpg"}]
    removed = attachment_file_urls_removed(before, after)
    assert len(removed) == 1
    assert removed[0] == "https://x/b.jpg"
