# Product brief: Seattle permit map

## What it is

A live, shareable, Redfin-style map of open Seattle building permits. You search an address, see what could get built nearby, and click a permit for details. The dbt medallion (bronze / silver / gold on DuckLake) and a semantic layer exist to serve the app. Anonymous engagement events flow back into the same warehouse.

The earlier LLM-accuracy benchmark is dropped; its brief and eval questions are kept in `docs/archive/`.

## The user

A neighbor or homebuyer, and specifically the PM himself. Every design choice is judged by one question: "would I use this when looking at a house?"

- **Open permit:** any permit not expired, completed/finaled, closed, canceled or withdrawn. Applied, in review, issued and under inspection all count: anything that could still get built.
- **Map:** address search zooms to the address with a 1,000 ft ring. Pins are colored by stage. Filters: stage, work type (new building, addition/alteration, demolition, ADU), minimum valuation, applied-within. A pin opens a side panel (address, description, work type, stage, key dates, valuation, units added/removed, contractor, link to the city permit page). A list view shows permits in view, sorted by distance.
- **Engagement:** anonymous product analytics, no login. Searches, permit clicks, filter use and similar events. Raw IPs are never stored (only a daily-salted hash). Accounts, watchlists and alerts come later, and only if people beyond the PM use it.

## v1 finish line (target 2026-11-13)

The PM sends a friend a URL. They search an address, see open permits on a map, click one and get details. Permit data refreshes daily with no manual step, and engagement events are captured live.

Post-v1: Raspberry Pi migration, accounts, alerts.

## Data

| Source | Use | Refresh |
|---|---|---|
| SDCI building permits (Seattle Open Data, Socrata) | The permits on the map | Daily |
| Seattle neighborhood geography | "In Ballard" and similar | Occasional |
| Engagement events (the app itself) | What people search and click | Live |

Build-time work uses committed synthetic fixtures in `tests/fixtures/`; the first real Socrata pull happens on the server.

## Architecture

```
Socrata (daily, Dagster OSS) → DuckLake bronze → dbt silver → gold (fct_open_permits)
                                                            → semantic model (open_permit_count, stage, work_type)
FastAPI + MapLibre app  ← gold
App events → Redis 8 Stream (events:v1) → drain → Parquet landing → DuckLake
```

- Storage: DuckLake with a SQLite catalog, via DuckDB. No Postgres.
- Redis 8: live event inbox (stream + consumer group) and, later, an API response cache.
- Hosting: one Hetzner ARM VPS running Coolify, the whole stack in one Docker Compose file; later the same setup on a Raspberry Pi. Budget $15–20/mo.

## Out of scope for v1

- Business licenses and food inspections
- Accounts, watchlists, alerts
- The LLM accuracy benchmark
- An "under inspection" stage until inspection data is added (open question)
