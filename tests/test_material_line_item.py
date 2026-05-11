from __future__ import annotations

import unittest

import pytest

from app.entities import MaterialLineItem


class TestMaterialLineItem(unittest.TestCase):
    def test_total_price_calculation(self) -> None:
        item = MaterialLineItem(material_id=1, name="Soil", quantity=10, unit_price=5)
        self.assertEqual(item.total_price, 50)


def test_material_line_item_creation() -> None:
    item = MaterialLineItem(material_id=1, description="Soil", quantity=10, unit_price=5.0)
    assert item.material_id == 1
    assert item.description == "Soil"
    assert item.quantity == 10
    assert item.unit_price == 5.0
    assert item.gst_inclusive is True

    with pytest.raises(AssertionError, match="Quantity must be greater than zero"):
        MaterialLineItem(material_id=2, description="Mulch", quantity=0, unit_price=5.0)

    with pytest.raises(AssertionError, match="Unit price cannot be negative"):
        MaterialLineItem(material_id=3, description="Mulch", quantity=5, unit_price=-1.0)


if __name__ == "__main__":
    unittest.main()
