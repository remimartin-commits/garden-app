from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.main import app


class TestDashboard(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_get_dashboard(self) -> None:
        response = self.client.get("/api/v1/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn("jobs", response.json())
        self.assertIn("revenue", response.json())


if __name__ == "__main__":
    unittest.main()
