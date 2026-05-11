from __future__ import annotations

import unittest
from datetime import datetime

import pytest

from app.entities import (
    AuditLog,
    BusinessProfile,
    ChecklistItem,
    CustomizationSetting,
    Job,
    JobPhoto,
    JobStatusDefinition,
    NotificationLog,
    OwnerUser,
    Payment,
    Property,
    Quote,
    RecurringJobRule,
)


class TestBusinessProfile(unittest.TestCase):
    def test_business_profile_initialization(self) -> None:
        profile = BusinessProfile(
            name="GardenOps",
            gst_number="12-345-678-901",
            address="123 Garden Lane, Christchurch",
            contact_email="ops@gardenops.test",
            phone_number="+64-123-456-789",
        )
        self.assertEqual(profile.name, "GardenOps")
        self.assertEqual(profile.gst_number, "12-345-678-901")

    def test_business_profile_validation(self) -> None:
        with self.assertRaises(ValueError):
            BusinessProfile(
                name="",
                gst_number="12-345-678-901",
                address="123 Garden Lane",
                contact_email="x@test.com",
                phone_number="+64",
            )


class TestOwnerUser(unittest.TestCase):
    def setUp(self) -> None:
        self.owner_user = OwnerUser(
            id=1,
            username="owner123",
            email="owner@example.com",
            is_active=True,
        )

    def test_owner_user_creation(self) -> None:
        self.assertEqual(self.owner_user.id, 1)
        self.assertEqual(self.owner_user.username, "owner123")
        self.assertEqual(self.owner_user.email, "owner@example.com")
        self.assertTrue(self.owner_user.is_active)


class TestProperty(unittest.TestCase):
    def test_property_initialization(self) -> None:
        prop = Property(property_id=1, owner_id=101, address="123 Garden Lane")
        self.assertEqual(prop.property_id, 1)
        self.assertEqual(prop.owner_id, 101)
        self.assertEqual(prop.address, "123 Garden Lane")

    def test_property_post_init_validation(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            Property(property_id=-1, owner_id=101, address="123 Garden Lane")
        self.assertIn("property_id", str(ctx.exception).lower())


class TestJob(unittest.TestCase):
    def test_create_job(self) -> None:
        job = Job(
            job_id=1,
            customer_id=101,
            property_id=201,
            description="Maintenance visit",
            workflow_status="Scheduled",
            scheduled_date="2023-11-01",
        )
        self.assertEqual(job.customer_id, 101)
        self.assertEqual(job.property_id, 201)
        self.assertEqual(job.workflow_status, "Scheduled")

    def test_empty_scheduled_date_raises_error(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            Job(
                job_id=2,
                customer_id=102,
                property_id=202,
                description="Cleanup",
                workflow_status="Pending",
                scheduled_date="",
            )
        self.assertIn("scheduled", str(ctx.exception).lower())


class TestChecklistItem(unittest.TestCase):
    def test_checklist_item_creation(self) -> None:
        item = ChecklistItem(description="Mow the lawn", is_completed=False)
        self.assertEqual(item.description, "Mow the lawn")
        self.assertFalse(item.is_completed)


class TestJobStatusDefinition(unittest.TestCase):
    def test_job_status_definition_initialization(self) -> None:
        status = JobStatusDefinition(name="Scheduled", description="Job is scheduled")
        self.assertEqual(status.name, "Scheduled")
        self.assertEqual(status.description, "Job is scheduled")
        self.assertTrue(status.is_active)


class TestRecurringJobRule(unittest.TestCase):
    def test_recurring_job_rule_creation(self) -> None:
        rule = RecurringJobRule(rule_id=1, customer_id=10, cadence="weekly", interval_days=2)
        self.assertEqual(rule.rule_id, 1)
        self.assertEqual(rule.interval_days, 2)


class TestQuote(unittest.TestCase):
    def test_quote_creation(self) -> None:
        q = Quote(
            quote_id=1,
            customer_id=10,
            property_id=20,
            title="  Spring tidy  ",
            subtotal_ex_gst=200.0,
            gst_amount=30.0,
            total_inc_gst=230.0,
            status="  draft  ",
        )
        self.assertEqual(q.title, "Spring tidy")
        self.assertEqual(q.status, "draft")
        self.assertEqual(q.subtotal_ex_gst, 200.0)
        self.assertTrue(q.created_at)

    def test_quote_rejects_invalid_ids(self) -> None:
        with self.assertRaises(ValueError):
            Quote(
                quote_id=0,
                customer_id=1,
                property_id=1,
                title="x",
                subtotal_ex_gst=0.0,
                gst_amount=0.0,
                total_inc_gst=0.0,
                status="draft",
            )


class TestPayment(unittest.TestCase):
    def test_payment_creation(self) -> None:
        paid_at = datetime(2023, 10, 10, 0, 0, 0)
        payment = Payment(
            id=1,
            amount=100.0,
            date=paid_at,
            method="Credit Card",
            status="Completed",
            invoice_id=42,
        )
        self.assertEqual(payment.id, 1)
        self.assertEqual(payment.amount, 100.0)
        self.assertEqual(payment.date, paid_at)
        self.assertEqual(payment.invoice_id, 42)
        self.assertEqual(payment.method, "Credit Card")
        self.assertEqual(payment.status, "Completed")


class TestJobPhoto(unittest.TestCase):
    def test_jobphoto_creation(self) -> None:
        ts = datetime(2024, 1, 1, 12, 0, 0)
        photo = JobPhoto(id=1, job_id=101, photo_url="http://example.com/photo.jpg", timestamp=ts)
        self.assertEqual(photo.id, 1)
        self.assertEqual(photo.job_id, 101)
        self.assertEqual(photo.photo_url, "http://example.com/photo.jpg")

    def test_empty_photo_url(self) -> None:
        with self.assertRaises(ValueError):
            JobPhoto(
                id=2,
                job_id=102,
                photo_url="",
                timestamp=datetime.now(),
            )


def test_customization_setting_initialization() -> None:
    setting = CustomizationSetting(
        name="Timezone",
        description="Set the default timezone",
        default_value="UTC",
    )
    assert setting.name == "Timezone"
    assert setting.description == "Set the default timezone"
    assert setting.default_value == "UTC"
    assert setting.current_value == "UTC"
    assert setting.owner_controlled is True


def test_customization_setting_validation() -> None:
    with pytest.raises(ValueError, match="Name must be provided for CustomizationSetting."):
        CustomizationSetting(name="", description="Invalid setting without a name")


class TestNotificationLog(unittest.TestCase):
    def test_notification_log_initialization(self) -> None:
        log = NotificationLog(id=1, message="Test Message", created_at=datetime.now())
        self.assertEqual(log.id, 1)
        self.assertEqual(log.message, "Test Message")
        self.assertFalse(log.read)

    def test_notification_log_created_at_validation(self) -> None:
        with self.assertRaises(ValueError):
            NotificationLog(id=1, message="Invalid", created_at="not a datetime")  # type: ignore[arg-type]

    def test_notification_log_creation(self) -> None:
        log = NotificationLog(
            id=1,
            message="Test message",
            recipient="test@example.com",
            sent_at=datetime.now(),
            status="sent",
        )
        self.assertEqual(log.status, "sent")

    def test_notification_log_invalid_status(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            NotificationLog(
                id=2,
                message="Test message",
                recipient="test@example.com",
                sent_at=datetime.now(),
                status="invalid",
            )
        self.assertEqual(str(ctx.exception), "Invalid status: invalid")


class TestAuditLog(unittest.TestCase):
    def test_audit_log_creation(self) -> None:
        log = AuditLog(id=1, action="create", entity="Job", entity_id=123)
        self.assertEqual(log.id, 1)
        self.assertEqual(log.action, "create")
        self.assertEqual(log.entity, "Job")
        self.assertEqual(log.entity_id, 123)
        self.assertIsInstance(log.timestamp, datetime)


if __name__ == "__main__":
    unittest.main()
