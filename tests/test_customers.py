from __future__ import annotations
import unittest
from app.entities import CustomerProfile

class TestCustomerAPI(unittest.TestCase):
    def test_create_and_retrieve_customer(self):
        customer = CustomerProfile(name='Redcliffs GardenOps', contact='Contact Person', property_details={'address': '123 Redcliffs', 'garden_profile': {}, 'access_instructions': 'Through the back gate', 'hazards': 'Bees'})
        self.assertEqual(customer.name, 'Redcliffs GardenOps')

if __name__ == '__main__':
    unittest.main()