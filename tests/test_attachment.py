from __future__ import annotations

import unittest

from app.entities import Attachment


class TestAttachment(unittest.TestCase):
    def test_attachment_creation(self) -> None:
        attachment = Attachment(id=1, filename="sample.jpg", file_url="http://example.com/sample.jpg")
        self.assertEqual(attachment.id, 1)
        self.assertEqual(attachment.filename, "sample.jpg")
        self.assertEqual(attachment.file_url, "http://example.com/sample.jpg")


if __name__ == "__main__":
    unittest.main()
