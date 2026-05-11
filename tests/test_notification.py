from __future__ import annotations

from app.entities import NotificationLog


def test_notification_log_related_entity_fields() -> None:
    log = NotificationLog(
        id=1,
        message="queued",
        related_entity_type="job",
        related_entity_id=123,
    )
    assert log.related_entity_id == 123
    assert log.related_entity_type == "job"
