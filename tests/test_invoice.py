from __future__ import annotations

import unittest
from datetime import date

from app.entities import Invoice


class TestInvoice(unittest.TestCase):
    def test_invoice_creation(self) -> None:
        invoice = Invoice(
            invoice_id=1,
            customer_id=100,
            amount=250.00,
            status="Pending",
            issue_date=date(2023, 10, 20),
            due_date=date(2023, 11, 20),
        )
        self.assertEqual(invoice.invoice_id, 1)
        self.assertEqual(invoice.customer_id, 100)
        self.assertEqual(invoice.amount, 250.00)
        self.assertEqual(invoice.status, "Pending")
        self.assertEqual(invoice.issue_date, date(2023, 10, 20))
        self.assertEqual(invoice.due_date, date(2023, 11, 20))


if __name__ == "__main__":
    unittest.main()
