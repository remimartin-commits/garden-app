from __future__ import annotations

import unittest
from app.entities import Payment
from datetime import datetime

class TestPayment(unittest.TestCase):

    def test_payment_initialization(self):
        payment = Payment(id=1, amount=100.0, date=datetime.now(), method='Credit Card', status='Completed', invoice_id=123)
        self.assertEqual(payment.amount, 100.0)
        self.assertEqual(payment.method, 'Credit Card')
        self.assertEqual(payment.status, 'Completed')

if __name__ == '__main__':
    unittest.main()