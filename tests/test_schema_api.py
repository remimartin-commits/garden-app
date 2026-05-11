
from __future__ import annotations
import unittest
from app.schema_api import app

class TestSchemaAPI(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()

    def test_get_existing_schema(self):
        response = self.app.get('/api/v1/settings/schemas/garden')
        self.assertEqual(response.status_code, 200)
        self.assertIn('properties', response.json)

    def test_get_non_existing_schema(self):
        response = self.app.get('/api/v1/settings/schemas/nonexistent')
        self.assertEqual(response.status_code, 404)

if __name__ == "__main__":
    unittest.main()
