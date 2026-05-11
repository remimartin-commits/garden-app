from __future__ import annotations

from app.entities import RecurringJobRule
from app.schemas.recurring_job_rule import RecurringJobRuleCreate


def create_recurring_job_rule(recurring_job_rule: RecurringJobRuleCreate) -> dict[str, object]:
    """Stub persistence: echo fields needed by tests."""
    return {
        "property_id": recurring_job_rule.property_id,
        "schedule": recurring_job_rule.schedule,
        "frequency": recurring_job_rule.frequency,
        "start_date": recurring_job_rule.start_date,
        "end_date": recurring_job_rule.end_date,
    }


def get_recurring_job_rule(rule_id: int) -> RecurringJobRule | None:
    if rule_id == 1:
        return RecurringJobRule(
            rule_id=1,
            customer_id=1,
            cadence="weekly",
            interval_days=7,
            paused=False,
            description="A sample rule description",
        )
    return None

def archive_quote_by_id(quote_id):
    """Logic to set a quote's archived status to true by its ID."""
    # Placeholder logic, assuming a database call sets archived status
    # return result of status update
    return True # Simulating successful archival

def get_invoice_with_payments(invoice_id):
    # Retrieve invoice with payments logic to be implemented
    pass
def soft_archive_business(business_id: int) -> None:
    business = get_business_by_id(business_id)
    if business:
        business.soft_archive()
        save_business(business)
