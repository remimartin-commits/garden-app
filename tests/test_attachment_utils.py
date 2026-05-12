from __future__ import annotations

from app.attachment_utils import coerce_attachments_list, safe_image_filename


def test_coerce_attachments_list_filters_invalid() -> None:
    assert coerce_attachments_list(None) == []
    assert coerce_attachments_list([{"filename": "a.jpg", "file_url": "https://x/a"}]) == [
        {"filename": "a.jpg", "file_url": "https://x/a"}
    ]
    assert coerce_attachments_list([{"filename": "", "file_url": "https://x"}]) == []


def test_safe_image_filename() -> None:
    assert safe_image_filename("weird name!!.jpeg", "png").endswith(".jpg")
    assert safe_image_filename("noext", "png").endswith(".png")
