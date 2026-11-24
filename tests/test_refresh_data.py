import unittest
from datetime import date

from refresh_data import freshness, latest_date, number, period_age_days


class RefreshDataTests(unittest.TestCase):
    def test_marks_period_stale_after_threshold(self):
        result = freshness("2026-09-30T00:00:00.000", date(2026, 11, 24))

        self.assertEqual(period_age_days(result["latest_period"], date(2026, 11, 24)), 55)
        self.assertTrue(result["is_stale"])

    def test_recent_period_is_not_stale(self):
        result = freshness("2026-11-20", date(2026, 11, 24))

        self.assertEqual(period_age_days(result["latest_period"], date(2026, 11, 24)), 4)
        self.assertFalse(result["is_stale"])

    def test_stale_status_stays_stable_between_daily_checks(self):
        first = freshness("2026-09-30", date(2026, 11, 24))
        next_day = freshness("2026-09-30", date(2026, 11, 25))

        self.assertEqual(first, next_day)

    def test_latest_date_uses_maximum_record_date(self):
        rows = [
            {"service_date": "2026-09-29T00:00:00.000"},
            {"service_date": "2026-09-30T00:00:00.000"},
            {"service_date": "2026-09-28T00:00:00.000"},
        ]

        self.assertEqual(latest_date(rows, "service_date"), "2026-09-30")

    def test_number_preserves_integer_and_decimal_values(self):
        self.assertEqual(number("1200"), 1200)
        self.assertEqual(number("1200.5"), 1200.5)


if __name__ == "__main__":
    unittest.main()
