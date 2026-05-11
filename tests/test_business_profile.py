from __future__ import annotations

import unittest

from app.entities import BusinessProfile


from app.entities import BusinessProfile
from app.config import convert_to_local_time, get_utc_now
import unittest

class TestBusinessProfile(unittest.TestCase):
    def test_initialization(self) -> None:
        profile = BusinessProfile(
            name="GardenOps",
            gst_number="123-456-789",
            address="123 Redcliffs Rd",
            contact_email="info@gardenops.nz",
            phone_number="0211234567",
        )
        self.assertEqual(profile.name, "GardenOps")
        self.assertEqual(profile.gst_number, "123-456-789")
        self.assertEqual(profile.address, "123 Redcliffs Rd")
        self.assertEqual(profile.contact_email, "info@gardenops.nz")
        self.assertEqual(profile.phone_number, "0211234567")


if __name__ == "__main__":
    unittest.main()
