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

## How this repo is built

Spec-driven with [OpenSpec](https://github.com/Fission-AI/OpenSpec). Design sessions use the `brainstorming` skill from [obra/superpowers](https://github.com/obra/superpowers) and `grill-me` from [mattpocock/skills](https://github.com/mattpocock/skills) (both MIT; licenses kept alongside each skill). Approved changes are implemented by agents and land as pull requests. See `CLAUDE.md`.
