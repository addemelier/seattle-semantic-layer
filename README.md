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

## Deploy

The live map runs on a Raspberry Pi 5 at home with [Coolify](https://coolify.io), public through a Cloudflare Tunnel. `docker-compose.yml` defines four services from one image: `app` (the map), `dagster-daemon` (the 5:00am refresh, plus the first pull on a fresh server), `dagster-webserver` (the Dagster UI, private) and `redis` (engagement events). Steps on the Pi:

1. Check the Pi runs 64-bit Raspberry Pi OS (`uname -m` prints `aarch64`), update it (`sudo apt update && sudo apt full-upgrade`), and give it a fixed address on your router.
2. Install Coolify with its one-line installer (see the coolify.io docs). Open `http://<pi-lan-ip>:8000` from your home network and create the admin account immediately.
3. Buy a domain (or move one) to Cloudflare. In Cloudflare: Networking → Tunnels → Create tunnel, choose Docker, and copy only the token.
4. In Coolify: + New → search "Cloudflared" → paste the token as its environment variable → deploy. In Cloudflare, add a route to the tunnel: subdomain `*`, your domain, service `http://localhost:80` (use `http://127.0.0.1:80` if that fails).
5. Coolify dashboard and auto-deploy: in Coolify Settings, set the instance domain to `https://coolify.<domain>`. In Cloudflare Zero Trust → Access, add an application for `coolify.<domain>` allowing only your email, and a second one for `coolify.<domain>/webhooks` with a Bypass policy so GitHub can reach it.
6. In Coolify: Sources → GitHub App (install it on this repo only), then + New Resource from the repo, build pack Docker Compose, file `docker-compose.yml`.
7. Set `EVENT_IP_SALT` in the resource's environment variables; generate a value with `openssl rand -hex 32`. The stack refuses to start without it.
8. On the `app` service, set the domain to `https://map.<domain>`, set "Redirect HTTP to HTTPS" to Disabled (the tunnel reaches Coolify over HTTP; leaving it on causes too many redirects), turn on auto-deploy, and deploy. Within minutes the map shows "Permits as of" today.
9. Dagster UI: from your home network, `ssh -L 3000:127.0.0.1:3000 <user>@<pi-lan-ip>`, then open <http://localhost:3000>.
10. If the first pull is rejected, the Dagster daemon log and `lake.bronze.ingest_runs` show the reason (a missing-columns rejection lists what Socrata sent).

Notes:

- No backups yet. Permit data can be re-pulled; engagement events in Redis would be lost with the Pi.
- The Pi boots from its SD card for now; an NVMe SSD comes later.
- Every merge to `main` redeploys automatically.
- Moving to a VPS later is the same Compose file without the tunnel, with the three volumes (`lake`, `redis_data`, `dagster_home`) copied over.

## How this repo is built

Spec-driven with [OpenSpec](https://github.com/Fission-AI/OpenSpec). Design sessions use the `brainstorming` skill from [obra/superpowers](https://github.com/obra/superpowers) and `grill-me` from [mattpocock/skills](https://github.com/mattpocock/skills) (both MIT; licenses kept alongside each skill). Approved changes are implemented by agents and land as pull requests. See `CLAUDE.md`.
