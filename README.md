# Chicago Transit Data

A Python data pipeline for the Chicago ridership dashboard on
`madisynshurtz.com/analytics/cta`. It refreshes CTA-published datasets from the
City of Chicago Data Portal and writes a small manifest plus one JSON snapshot
per year. The dashboard fetches only the selected year's file, then lets users
filter by month.

## What the counts mean

- Daily systemwide, bus, and rail totals are boarding/rides counts, not unique
  people. A person can be counted more than once.
- Bus routes are ranked by `monthtotal`, the dataset's monthly route total.
  The source also contains average weekday rides, but the dashboard does not
  use that measure.
- Rail station totals sum the source's daily station entries by station and
  month. These are entry/boarding events, not unique passengers.

## Data sources and freshness

- Daily bus and rail totals: [dataset 6iiy-9s97](https://data.cityofchicago.org/d/6iiy-9s97)
- Monthly bus route totals: [dataset bynn-gwxy](https://data.cityofchicago.org/d/bynn-gwxy)
- Daily rail station entries: [dataset 5neh-572f](https://data.cityofchicago.org/d/5neh-572f)

The manifest records each dataset's latest available period and last portal
update time. A period older than 45 days is flagged as stale; this is a warning,
not a claim about CTA's publication schedule. At initial setup, daily and
station records ended on September 30, 2026, while the bus-route data ended in
September 2026. Scheduled refreshes can detect new records but cannot fill in
data the source has not released.

## Run locally

Requires Python 3.10 or later; there are no third-party packages.

```powershell
python refresh_data.py
python -m unittest discover -s tests -v
```

The pipeline writes `data/cta-ridership.json` as a manifest and files named
`data/cta-ridership-YYYY.json` for each year present in the source.

## GitHub repository

The public repository is [mshurtz51/Chicago_CTA](https://github.com/mshurtz51/Chicago_CTA).

The dashboard uses:

- Manifest: `https://raw.githubusercontent.com/mshurtz51/Chicago_CTA/main/data/cta-ridership.json`
- Yearly data: `https://raw.githubusercontent.com/mshurtz51/Chicago_CTA/main/data/cta-ridership-YYYY.json`

If the repository owner or name changes, update `snapshotBase` in the website's
`cta.js`.

## Scheduled refreshes

The GitHub Actions workflow runs daily and can also be started manually from
the repository's **Actions** tab. It commits changed manifests and yearly
snapshots only, avoiding empty daily commits. The workflow needs the
`contents: write` permission, already declared in its workflow settings.

No secrets or API keys are needed for these historical datasets. If the next
phase adds CTA's live Bus Tracker or Train Tracker APIs, keep the issued key in
GitHub Actions Secrets and use a persistent collector for frequent sampling;
scheduled GitHub Actions are not a real-time data service.
