#!/usr/bin/env python3
"""Refresh yearly CTA ridership snapshots used by the website."""

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
PAGE_SIZE = 50000
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


def fetch_all_rows(dataset_id, params):
    rows = []
    offset = 0
    while True:
        page = fetch_rows(dataset_id, {
            **params,
            "$limit": str(PAGE_SIZE),
            "$offset": str(offset),
        })
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


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
    return {
        "latest_period": latest_period[:10],
        "stale_after_days": STALE_AFTER_DAYS,
        "is_stale": period_age_days(latest_period, today) > STALE_AFTER_DAYS,
    }


def build_snapshots(daily_rows, route_rows, station_rows, source_updates, today=None):
    if not daily_rows:
        raise ValueError("The daily ridership dataset returned no records")
    if not route_rows:
        raise ValueError("The bus-route dataset returned no records")
    if not station_rows:
        raise ValueError("The rail-station dataset returned no records")

    by_year = {}

    def year_data(year):
        return by_year.setdefault(year, {
            "daily_ridership": [],
            "bus_routes": [],
            "rail_stations": [],
        })

    daily_dates = []
    for row in daily_rows:
        day = str(row["service_date"])[:10]
        daily_dates.append(day)
        year_data(int(day[:4]))["daily_ridership"].append({
            "date": day,
            "day_type": row["day_type"],
            "bus": number(row["bus"]),
            "rail_boardings": number(row["rail_boardings"]),
            "total_rides": number(row["total_rides"]),
        })

    route_months = []
    for row in route_rows:
        month = str(row["month_beginning"])[:10]
        route_months.append(month)
        year_data(int(month[:4]))["bus_routes"].append({
            "route": row["route"],
            "name": row["routename"],
            "month": month,
            "month_total": number(row["monthtotal"]),
        })

    station_dates = []
    for row in station_rows:
        month = str(row["month"])[:10]
        station_dates.append(str(row.get("latest_date", month))[:10])
        year_data(int(month[:4]))["rail_stations"].append({
            "name": row["stationname"],
            "month": month,
            "rides": number(row["rides"]),
        })

    latest_periods = {
        "daily_ridership": max(daily_dates),
        "bus_routes": max(route_months),
        "rail_stations": max(station_dates),
    }
    dataset_names = {
        "daily_ridership": "daily",
        "bus_routes": "bus_routes",
        "rail_stations": "rail_stations",
    }
    sources = {
        name: {
            **freshness(latest_period, today),
            "source_updated_at": source_updates[dataset_names[name]],
            "source_url": DATASETS[dataset_names[name]]["url"],
        }
        for name, latest_period in latest_periods.items()
    }

    yearly_snapshots = {
        year: {
            "schema_version": 2,
            "year": year,
            "daily_ridership": {"rows": sections["daily_ridership"]},
            "bus_routes": {"rows": sections["bus_routes"]},
            "rail_stations": {"rows": sections["rail_stations"]},
        }
        for year, sections in sorted(by_year.items())
    }
    manifest = {
        "schema_version": 2,
        "years": sorted(yearly_snapshots, reverse=True),
        "sources": sources,
    }
    return {"manifest": manifest, "years": yearly_snapshots}


def collect_snapshot(today=None):
    next_year = date.today().year + 1
    end_date = f"{next_year}-01-01T00:00:00"
    daily_rows = fetch_all_rows(DATASETS["daily"]["id"], {
        "$select": "service_date,day_type,bus,rail_boardings,total_rides",
        "$where": f"service_date < '{end_date}'",
        "$order": "service_date ASC",
    })
    route_rows = fetch_all_rows(DATASETS["bus_routes"]["id"], {
        "$select": "route,routename,month_beginning,monthtotal",
        "$where": f"month_beginning < '{end_date}'",
        "$order": "month_beginning ASC,route ASC",
    })
    station_rows = fetch_all_rows(DATASETS["rail_stations"]["id"], {
        "$select": "date_trunc_ym(date) as month,stationname,sum(rides) as rides,max(date) as latest_date",
        "$where": f"date < '{end_date}'",
        "$group": "month,stationname",
        "$order": "month ASC,stationname ASC",
    })
    source_updates = {
        name: fetch_dataset_metadata(dataset["id"])
        for name, dataset in DATASETS.items()
    }
    return build_snapshots(
        daily_rows,
        route_rows,
        station_rows,
        source_updates,
        today,
    )


def write_json(path, data):
    serialized = json.dumps(data, indent=2, sort_keys=True) + "\n"
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(serialized, encoding="utf-8")
    temporary_path.replace(path)


def write_snapshot(snapshot, output_path=OUTPUT_PATH):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    for year, data in snapshot["years"].items():
        yearly_path = output_path.with_name(f"cta-ridership-{year}.json")
        write_json(yearly_path, data)
    write_json(output_path, snapshot["manifest"])


def main():
    snapshot = collect_snapshot()
    write_snapshot(snapshot)
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"Checked City of Chicago data at {checked_at}")
    print(
        "Published yearly snapshots: "
        + ", ".join(map(str, snapshot["manifest"]["years"]))
    )
    for name, dataset in snapshot["manifest"]["sources"].items():
        freshness_status = "STALE" if dataset["is_stale"] else "current"
        print(
            f"{name}: latest {dataset['latest_period']}, "
            f"{period_age_days(dataset['latest_period'])} days old ({freshness_status})"
        )


if __name__ == "__main__":
    main()
