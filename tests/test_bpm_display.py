"""Field-scoped numeric DOM display comparisons, independent of plan sources."""
import unittest
from decimal import Decimal

from bpm.verify import decimal, values_equal


class DisplayNormalizationTests(unittest.TestCase):
    def test_grouped_money_and_count_compare_exactly(self):
        self.assertEqual(decimal("1,234.50"), Decimal("1234.50"))
        self.assertEqual(decimal("123,456,789.00001"), Decimal("123456789.00001"))
        self.assertTrue(values_equal("totalCost", "1234.50", "1,234.50"))
        self.assertTrue(values_equal("cost", "1234567.89", "1,234,567.89"))
        self.assertTrue(values_equal("count", "1000", "1,000"))
        self.assertFalse(values_equal("cost", "1234.50", "1,234.50001"))

    def test_malformed_grouping_and_nonfinite_values_rejected(self):
        for text in ("12,34.50", "1234,567.89", "1,23,456", "1,,234", "0,123", "001,234",
                     "1,234.", "1,234e2", " 1,234.50", "1,234.50 ", "NaN", "Infinity", "-Infinity"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    decimal(text)
                self.assertFalse(values_equal("cost", "1234.50", text))

    def test_accounts_and_business_identifiers_keep_exact_characters(self):
        self.assertTrue(values_equal("account", "001234", "001234"))
        self.assertFalse(values_equal("account", "001234", "1234"))
        self.assertFalse(values_equal("account", "001234", "001,234"))
        self.assertFalse(values_equal("account", "1234", "1,234"))
        self.assertFalse(values_equal("bankCode", "001234", "001,234"))
        self.assertFalse(values_equal("bizNumber", "12026000001", "12,026,000,001"))


if __name__ == "__main__":
    unittest.main()
