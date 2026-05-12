from __future__ import annotations

from tests.http_helpers import auth_test_client

import unittest

from fastapi.testclient import TestClient

from app.entities import NotificationLog
from app.main import app

client = auth_test_client()


class TestNotificationLog(unittest.TestCase):
    def test_create_notification_log(self) -> None:
        log = NotificationLog(
            id=1,
            message="queued",
            related_entity_type="job",
            related_entity_id=1,
        )
        self.assertEqual(log.related_entity_type, "job")
        self.assertEqual(log.related_entity_id, 1)


def test_post_notify_customer_creates_notification_log() -> None:
    response = client.post("/api/v1/jobs/1/notify-customer")
    assert response.status_code == 200
    data = response.json()
    assert data["related_entity_type"] == "job"
    assert data["related_entity_id"] == 1


if __name__ == "__main__":
    unittest.main()
