#!/usr/bin/env python3
"""Refresh the public CTA ridership snapshot used by the website."""

import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
OUTPUT_PATH = ROOT / "data" / "cta-ridership.json"
PORTAL = "https://data.cityofchicago.org"
STALE_AFTER_DAYS = 45
DATASETS = {
    "daily": {
        "id": "6iiy-9s97",
        "url": "https://data.cityofchicago.org/d/6iiy-9s97",
    },
    "bus_routes": {
        "id": "bynn-gwxy",
        "url": "https://data.cityofchicago.org/d/bynn-gwxy",
    },
    "rail_stations": {
        "id": "5neh-572f",
        "url": "https://data.cityofchicago.org/d/5neh-572f",
    },
}


def fetch_json(url):
    request = Request(url, headers={"User-Agent": "ChicagoTransitData/1.0"})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_rows(dataset_id, params):
    query = urlencode(params)
    url = f"{PORTAL}/resource/{dataset_id}.json?{query}"
    rows = fetch_json(url)
    if not isinstance(rows, list):
        raise ValueError(f"Dataset {dataset_id} returned a non-list response")
    return rows


def fetch_dataset_metadata(dataset_id):
    metadata = fetch_json(f"{PORTAL}/api/views/{dataset_id}.json")
    updated_at = datetime.fromtimestamp(
        int(metadata["rowsUpdatedAt"]), timezone.utc
    ).isoformat(timespec="seconds").replace("+00:00", "Z")
    return updated_at


def latest_date(rows, field):
    dates = [str(row[field])[:10] for row in rows if row.get(field)]
    if not dates:
        raise ValueError(f"No records contain the expected {field} date")
    return max(dates)


def number(value):
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"Expected a finite number, got {value!r}")
    return int(parsed) if parsed.is_integer() else parsed


def period_age_days(latest_period, today=None):
    today = today or date.today()
    return (today - date.fromisoformat(latest_period[:10])).days


def freshness(latest_period, today=None):
    age_days = period_age_days(latest_period, today)
    return {
        "latest_period": latest_period[:10],
        "stale_after_days": STALE_AFTER_DAYS,
        "is_stale": age_days > STALE_AFTER_DAYS,
    }


def collect_snapshot(today=None):
    daily_source = DATASETS["daily"]
    daily_rows = fetch_rows(daily_source["id"], {
        "$select": "service_date,day_type,bus,rail_boardings,total_rides",
        "$order": "service_date DESC",
        "$limit": "14",
    })
    if not daily_rows:
        raise ValueError("The daily ridership dataset returned no records")
    daily_rows.sort(key=lambda row: row["service_date"])
    daily_period = latest_date(daily_rows, "service_date")
    daily_data = {
        **freshness(daily_period, today),
        "source_url": daily_source["url"],
        "source_updated_at": fetch_dataset_metadata(daily_source["id"]),
        "rows": [
            {
                "date": str(row["service_date"])[:10],
                "day_type": row["day_type"],
                "bus": number(row["bus"]),
                "rail_boardings": number(row["rail_boardings"]),
                "total_rides": number(row["total_rides"]),
            }
            for row in daily_rows
        ],
    }

    route_source = DATASETS["bus_routes"]
    route_period_rows = fetch_rows(route_source["id"], {
        "$select": "month_beginning",
        "$order": "month_beginning DESC",
        "$limit": "1",
    })
    if not route_period_rows:
        raise ValueError("The bus-route dataset returned no records")
    route_month = route_period_rows[0]["month_beginning"]
    route_rows = fetch_rows(route_source["id"], {
        "$select": "route,routename,month_beginning,avg_weekday_rides",
        "$where": f"month_beginning='{route_month}'",
        "$order": "avg_weekday_rides DESC",
        "$limit": "10",
    })
    if not route_rows:
        raise ValueError(f"No bus routes were returned for {route_month}")
    route_data = {
        **freshness(route_month, today),
        "source_url": route_source["url"],
        "source_updated_at": fetch_dataset_metadata(route_source["id"]),
        "rows": [
            {
                "route": row["route"],
                "name": row["routename"],
                "month_beginning": str(row["month_beginning"])[:10],
                "avg_weekday_rides": number(row["avg_weekday_rides"]),
            }
            for row in route_rows
        ],
    }

    station_source = DATASETS["rail_stations"]
    station_period_rows = fetch_rows(station_source["id"], {
        "$select": "date",
        "$order": "date DESC",
        "$limit": "1",
    })
    if not station_period_rows:
        raise ValueError("The rail station dataset returned no records")
    station_day = station_period_rows[0]["date"]
    station_rows = fetch_rows(station_source["id"], {
        "$select": "stationname,date,daytype,rides",
        "$where": f"date='{station_day}'",
        "$order": "rides DESC",
        "$limit": "10",
    })
    if not station_rows:
        raise ValueError(f"No rail stations were returned for {station_day}")
    station_data = {
        **freshness(station_day, today),
        "source_url": station_source["url"],
        "source_updated_at": fetch_dataset_metadata(station_source["id"]),
        "rows": [
            {
                "name": row["stationname"],
                "date": str(row["date"])[:10],
                "day_type": row["daytype"],
                "rides": number(row["rides"]),
            }
            for row in station_rows
        ],
    }

    return {
        "schema_version": 1,
        "daily_ridership": daily_data,
        "bus_routes": route_data,
        "rail_stations": station_data,
    }


def write_snapshot(snapshot, output_path=OUTPUT_PATH):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(snapshot, indent=2, sort_keys=True) + "\n"
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary_path.write_text(serialized, encoding="utf-8")
    temporary_path.replace(output_path)


def main():
    snapshot = collect_snapshot()
    write_snapshot(snapshot)
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"Checked City of Chicago data at {checked_at}")
    for name in ("daily_ridership", "bus_routes", "rail_stations"):
        dataset = snapshot[name]
        freshness_status = "STALE" if dataset["is_stale"] else "current"
        age_days = period_age_days(dataset["latest_period"])
        print(
            f"{name}: latest {dataset['latest_period']}, "
            f"{age_days} days old ({freshness_status})"
        )


if __name__ == "__main__":
    main()
