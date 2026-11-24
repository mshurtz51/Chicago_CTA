# Chicago Transit Data

A small Python data pipeline for the Chicago ridership dashboard on
`madisynshurtz.com/analytics/cta`. It downloads the CTA-published datasets from
the City of Chicago Data Portal, normalizes the current leaders and recent
history, and writes `data/cta-ridership.json`.

The dashboard reads that JSON from this public repository. If the repository
feed is unavailable during setup, the website temporarily falls back to the
same public Socrata API endpoints.

## Data sources and freshness

- Daily bus and rail totals: [dataset 6iiy-9s97](https://data.cityofchicago.org/d/6iiy-9s97)
- Monthly bus route averages: [dataset bynn-gwxy](https://data.cityofchicago.org/d/bynn-gwxy)
- Daily rail station entries: [dataset 5neh-572f](https://data.cityofchicago.org/d/5neh-572f)

The pipeline records each dataset's latest available period and last portal
update time. A period older than 45 days is marked stale; this is a warning,
not a claim about CTA's publication schedule. At initial setup, the portal's
daily and station datasets ended on September 30, 2026, while the bus-route
dataset ended in September 2026. A scheduled run can detect when CTA publishes
new rows, but cannot fill in records the source has not released.

## Run locally

Requires Python 3.10 or later; there are no third-party packages.

```powershell
python refresh_data.py
python -m unittest discover -s tests -v
```

## GitHub repository

The public repository is [mshurtz51/Chicago_CTA](https://github.com/mshurtz51/Chicago_CTA).

The website's feed URL is
`https://raw.githubusercontent.com/mshurtz51/Chicago_CTA/main/data/cta-ridership.json`.
If the repository owner or name changes, update `snapshotUrl` in the website's
`cta.js` to match.

## Scheduled refreshes

The GitHub Actions workflow runs daily and can also be started manually from
the repository's **Actions** tab. It commits the generated JSON only when the
published source data, its metadata, or its stale status changes, avoiding
empty daily commits. The workflow needs `contents: write`, already declared
in its permissions.

No secrets or API keys are needed for these historical datasets. If the next
phase adds CTA's live Bus Tracker or Train Tracker APIs, keep the issued key in
GitHub Actions Secrets and use a persistent collector for frequent sampling;
scheduled GitHub Actions are not a real-time data service.
