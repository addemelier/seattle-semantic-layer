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

## Engagement events

The page sends anonymous usage events to `POST /api/events`, which appends them to the Redis stream `events:v1`. Four kinds are sent:

- `search`: the address as typed (up to 200 characters), plus the matched point when the search succeeded
- `permit_click`: the permit id and the pin's coordinates
- `filter_change`: the checked stage and work-type boxes
- `map_move`: the map center once it settles, only at zoom 12 or closer and at most once every 2 seconds

Each event carries a random 32-character session ID kept in the browser's `localStorage` (renewed after 30 days unused) and `document.referrer`. The server adds the user agent and, only when `EVENT_IP_SALT` is set, a salted hash of the IP that changes every UTC day; raw IPs are never stored, and coordinates are rounded to 3 decimals. If the browser sends Global Privacy Control or Do Not Track, the page sends nothing. Sends are fire-and-forget: if Redis is down the endpoint answers 503 and the map carries on.

Settings:

- `REDIS_URL` (e.g. `redis://localhost:6379/0`): events are off when unset, and the endpoint answers 503 `events disabled`, so local runs on fixtures need no Redis.
- `EVENT_IP_SALT`: secret salt for the daily IP hash. Leave unset to store no IP hash at all. Never commit it.
- `PERMITMAP_TRUST_PROXY=1`: take the visitor IP from the left-most `X-Forwarded-For` address. Set it only behind a reverse proxy you control; otherwise the header is ignored, since anyone could forge it.

`python -m permitmap.drain_events` moves events from the stream to date-partitioned Parquet under `data/landing/events/` (it reads `REDIS_URL` too). Event data is never committed.

## How this repo is built

Spec-driven with [OpenSpec](https://github.com/Fission-AI/OpenSpec). Design sessions use the `brainstorming` skill from [obra/superpowers](https://github.com/obra/superpowers) and `grill-me` from [mattpocock/skills](https://github.com/mattpocock/skills) (both MIT; licenses kept alongside each skill). Approved changes are implemented by agents and land as pull requests. See `CLAUDE.md`.
