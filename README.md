# seattle-semantic-layer

A live, shareable Redfin-style map of open Seattle building permits: search an address, see what could get built nearby, and click a permit for details. Under it sits a dbt medallion on DuckLake and a semantic layer that define what an "open permit" is, plus anonymous engagement events that flow back into the same warehouse.

**Status:** in development, v1 target 2026-11-13.

## Stack

- Python 3.11+, DuckDB with DuckLake (SQLite catalog)
- dbt-core + dbt-duckdb, with a semantic model for the open-permit definitions
- Dagster OSS for the daily permit refresh
- Redis 8 (event stream, later a cache)
- FastAPI + MapLibre front end
- One Docker Compose file on a small VPS (later a Raspberry Pi)

Data: Seattle Open Data (SDCI building permits) via Socrata.

See [the product brief](docs/product-brief.md).

## Run it locally

Everything below runs on the synthetic fixtures in `tests/fixtures/`; no account or API key is needed.

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'

# Build the fixture lake (DuckLake catalog in data/lake/)
python -m permitmap.load_fixture
dbt build --project-dir dbt --profiles-dir dbt -s +fct_open_permits

# Start the map
python -m permitmap.app
```

Then open <http://127.0.0.1:8000>. The basemap (OpenFreeMap) and address search (City of Seattle locator) are fetched live, so those two need internet access. Settings are environment variables: `PERMITMAP_HOST`, `PERMITMAP_PORT`, `PERMITMAP_LAKE_CATALOG`, `PERMITMAP_LAKE_DATA`, `PERMITMAP_STYLE_URL`, `PERMITMAP_GEOCODER_URL`, `PERMITMAP_SOCRATA_URL`.

Tests: `python -m pytest -q`. The browser tests in `tests/ui/` use Playwright; point them at a local Chromium with `PW_CHROMIUM_PATH` if you don't want Playwright's own download.

## Daily refresh

Real permits come from the city's Socrata endpoint (`PERMITMAP_SOCRATA_URL`, default `https://cos-data.seattle.gov/resource/76t5-zqzr.csv`; no token needed). Each run pulls the full dataset, loads it to a side table, and swaps it into `lake.bronze.sdci_building_permits` only if every column the staging model reads is present and the valid row count is at least 90% of the last accepted run. A rejected run leaves yesterday's data on the map.

```bash
# One-off run: pull, check, swap, then dbt build. Exits 1 if the pull is rejected or dbt fails.
python -m permitmap.ingest

# Run the 5:00am America/Los_Angeles schedule (and the Dagster UI)
dbt parse --project-dir dbt --profiles-dir dbt   # writes the manifest Dagster reads
dagster dev -m permitmap.orchestration.definitions
```

Every run, accepted or rejected, appends a row to `lake.bronze.ingest_runs` (counts, `status`, and `reason` when rejected). Rows with a blank permit number or non-numeric coordinates go to `lake.bronze.sdci_building_permits_quarantine` with a `quarantine_reason`. To look at them:

```python
from permitmap.lake import connect_lake
con = connect_lake("data/lake/catalog.sqlite", "data/lake/files")
con.sql("SELECT * FROM lake.bronze.ingest_runs ORDER BY finished_at DESC LIMIT 10").show()
con.sql("SELECT quarantine_reason, count(*) FROM lake.bronze.sdci_building_permits_quarantine GROUP BY 1").show()
```

The map's bottom-left label shows "Permits as of <date>", turns amber after 36 hours without an accepted run, and reads "Sample data" on the fixture lake. `/healthz` reports the same freshness and stays 200 when data is stale.

## How this repo is built

Spec-driven with [OpenSpec](https://github.com/Fission-AI/OpenSpec). Design sessions use the `brainstorming` skill from [obra/superpowers](https://github.com/obra/superpowers) and `grill-me` from [mattpocock/skills](https://github.com/mattpocock/skills) (both MIT; licenses kept alongside each skill). Approved changes are implemented by agents and land as pull requests. See `CLAUDE.md`.
