from __future__ import annotations
from app.config import get_utc_now, convert_to_local_time
import unittest

class TestDatetimeHandling(unittest.TestCase):

    def test_get_utc_now(self):
        utc_now = get_utc_now()
        self.assertTrue(utc_now.endswith('Z'))

    def test_convert_to_local_time(self):
        utc_time = get_utc_now()
        local_time = convert_to_local_time(utc_time)
        self.assertIn('+', local_time)

if __name__ == "__main__":
    unittest.main()