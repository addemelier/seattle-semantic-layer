# Proposal: permit-map-destination

## Why

The repo's destination has changed (PM decision, 2026-10-02). It is no longer an LLM accuracy benchmark. It is a **live, Redfin-style map of open Seattle building permits** that the PM, as a neighbor or homebuyer, would use himself. The dbt layers and the semantic layer are built to serve that app.

This change resets the docs to the new destination and lays the data foundation: an offline, fixture-driven pipeline to a gold table of open permits on DuckLake, plus the live engagement-event capture on Redis.

## What changes

- The old benchmark brief and eval questions move to `docs/archive/`. A new product brief, README and the CLAUDE.md project constraints describe the permit map.
- A Python package `permitmap` with a DuckLake (SQLite catalog) connection helper that works fully offline.
- A committed **synthetic** fixture of SDCI building permits and neighborhood polygons, used for every build-time verification.
- A dbt project: bronze fixture load → `stg_sdci__building_permits` → gold `fct_open_permits`, implementing the "open permit", `stage` and `work_type` definitions, plus a semantic-model YAML for them.
- Engagement events: a function that writes anonymous events to a Redis Stream, and a drain step that moves them to date-partitioned Parquet.

## Capabilities

- `open-permits`: what counts as an open permit, its stage and work type, and the fields the gold table exposes.
- `engagement-events`: what an event contains, what is never stored, and how events reach the landing zone.

## Out of scope (later changes)

- Live Socrata ingest of SDCI permits and neighborhood boundaries (the build sandbox can't reach `data.seattle.gov`)
- The neighborhood spatial join (D4 geography)
- The "Under inspection" stage (needs SDCI inspection data, see design open questions)
- Dagster definitions and schedule; the FastAPI app; the MapLibre UI; Redis caching of API responses
- Docker Compose, Coolify and Hetzner deployment; Raspberry Pi migration
- Accounts, watchlists, alerts; D1 licenses and D3 food inspections

## Eval questions affected

None. The eval is archived (design D2).
