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

Then open <http://127.0.0.1:8000>. The basemap (OpenFreeMap) and address search (City of Seattle locator) are fetched live, so those two need internet access. Settings are environment variables: `PERMITMAP_HOST`, `PERMITMAP_PORT`, `PERMITMAP_LAKE_CATALOG`, `PERMITMAP_LAKE_DATA`, `PERMITMAP_STYLE_URL`, `PERMITMAP_GEOCODER_URL`.

Tests: `python -m pytest -q`. The browser tests in `tests/ui/` use Playwright; point them at a local Chromium with `PW_CHROMIUM_PATH` if you don't want Playwright's own download.

## How this repo is built

Spec-driven with [OpenSpec](https://github.com/Fission-AI/OpenSpec). Design sessions use the `brainstorming` skill from [obra/superpowers](https://github.com/obra/superpowers) and `grill-me` from [mattpocock/skills](https://github.com/mattpocock/skills) (both MIT; licenses kept alongside each skill). Approved changes are implemented by agents and land as pull requests. See `CLAUDE.md`.
