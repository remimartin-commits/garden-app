from __future__ import annotations

from tests.http_helpers import auth_test_client

import unittest

from fastapi.testclient import TestClient

from app.main import app


class TestDashboard(unittest.TestCase):
    def setUp(self) -> None:
        self.client = auth_test_client()

    def test_get_dashboard(self) -> None:
        response = self.client.get("/api/v1/dashboard")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("jobs", data)
        self.assertIn("revenue", data)
        self.assertIn("jobs_scheduled_today", data)
        self.assertIsInstance(data["jobs_scheduled_today"], int)


if __name__ == "__main__":
    unittest.main()
