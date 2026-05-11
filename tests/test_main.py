from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.main import app


class TestDashboardEndpoint(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_get_dashboard(self) -> None:
        response = self.client.get("/api/v1/dashboard")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("jobs", data)
        self.assertIn("revenue", data)
        self.assertIn("overdue_invoices", data)
        self.assertIn("upcoming_work", data)
        self.assertIn("weather_risks", data)
        self.assertIn("staff_availability", data)


if __name__ == "__main__":
    unittest.main()