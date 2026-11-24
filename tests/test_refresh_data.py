import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from refresh_data import (
    build_snapshots,
    freshness,
    latest_date,
    number,
    period_age_days,
    station_line_map,
    write_snapshot,
)


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

    def test_build_snapshots_partitions_years_and_uses_monthly_route_totals(self):
        source_updates = {
            "daily": "2026-11-20T00:00:00Z",
            "bus_routes": "2026-11-20T00:00:00Z",
            "rail_stations": "2026-11-20T00:00:00Z",
            "bus_route_daily": "2026-11-20T00:00:00Z",
            "rail_stops": "2026-11-20T00:00:00Z",
        }
        snapshot = build_snapshots(
            [
                {
                    "service_date": "2025-12-31T00:00:00.000",
                    "day_type": "W",
                    "bus": "100",
                    "rail_boardings": "50",
                    "total_rides": "150",
                },
                {
                    "service_date": "2026-01-01T00:00:00.000",
                    "day_type": "U",
                    "bus": "200",
                    "rail_boardings": "75",
                    "total_rides": "275",
                },
            ],
            [
                {
                    "route": "9",
                    "routename": "Ashland",
                    "month_beginning": "2026-01-01T00:00:00.000",
                    "monthtotal": "462170",
                },
            ],
            [
                {
                    "station_id": "40380",
                    "month": "2026-01-01T00:00:00.000",
                    "stationname": "Clark/Lake",
                    "rides": "262710",
                    "latest_date": "2026-01-31T00:00:00.000",
                },
            ],
            [
                {
                    "map_id": "40380",
                    "station_name": "Clark/Lake",
                    "blue": True,
                    "brn": False,
                    "g": True,
                    "o": False,
                    "pnk": False,
                    "p": False,
                    "red": False,
                    "y": False,
                },
                {
                    "map_id": "40380",
                    "station_name": "Clark/Lake",
                    "blue": False,
                    "brn": True,
                    "g": False,
                    "o": False,
                    "pnk": True,
                    "p": True,
                    "red": False,
                    "y": False,
                },
            ],
            source_updates,
            "2026-01-31",
            date(2026, 11, 24),
        )

        self.assertEqual(snapshot["manifest"]["years"], [2026, 2025])
        self.assertEqual(snapshot["manifest"]["schema_version"], 3)
        self.assertEqual(
            snapshot["manifest"]["sources"]["rail_stations"]["latest_period"],
            "2026-01-31",
        )
        self.assertEqual(
            snapshot["manifest"]["sources"]["daily_bus_routes"]["latest_period"],
            "2026-01-31",
        )
        self.assertEqual(
            snapshot["manifest"]["rail_station_lines"]["40380"]["lines"],
            ["Blue", "Brown", "Green", "Pink", "Purple"],
        )
        self.assertEqual(
            snapshot["years"][2026]["daily_ridership"]["rows"][0]["total_rides"],
            275,
        )
        self.assertEqual(
            snapshot["years"][2026]["bus_routes"]["rows"][0]["month_total"],
            462170,
        )
        self.assertEqual(
            snapshot["years"][2026]["rail_stations"]["rows"][0]["rides"],
            262710,
        )
        self.assertEqual(
            snapshot["years"][2026]["rail_stations"]["rows"][0]["station_id"],
            "40380",
        )
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "cta-ridership.json"
            write_snapshot(snapshot, manifest_path)
            saved_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            saved_year = json.loads(
                (Path(directory) / "cta-ridership-2026.json").read_text(
                    encoding="utf-8"
                )
            )
        self.assertEqual(saved_manifest["years"], [2026, 2025])
        self.assertEqual(saved_year["year"], 2026)

    def test_station_line_map_unions_lines_from_directional_stops(self):
        mapping = station_line_map([
            {"map_id": "41320", "station_name": "Belmont", "red": True, "brn": False, "p": False},
            {"map_id": "41320", "station_name": "Belmont", "red": False, "brn": True, "p": True},
        ])

        self.assertEqual(
            mapping["41320"]["lines"],
            ["Red", "Brown", "Purple"],
        )


if __name__ == "__main__":
    unittest.main()
