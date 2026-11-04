# Proposal: live-permits-ingest

## Why

The map works, but only on synthetic fixtures, so the PM can't use it while looking at a house. v1 (target 2026-11-13) needs "permit data refreshes daily with no manual step." This change replaces the fixture with a nightly full pull of the real SDCI permits dataset, guarded so that a bad night never blanks or shrinks the map, and tells the user how fresh the data is.

## What Changes

- A nightly job pulls the full SDCI building-permits dataset (Socrata `76t5-zqzr`, CSV) page by page and loads it into `lake.bronze.sdci_building_permits`, then rebuilds silver and gold with dbt.
- A pull is loaded to a side table first and swapped in only if it passes two checks: every column staging uses is present, and the valid row count hasn't dropped more than 10% from the last accepted load. Otherwise the previous data stays up.
- Malformed rows (blank permit number, or coordinates that aren't numbers) go to a quarantine table with a reason instead of bronze.
- Every run is logged in `lake.bronze.ingest_runs` (counts, accepted or rejected, and why).
- The same pipeline runs as a Dagster job on a 5:00am Pacific schedule and as a one-shot command (`python -m permitmap.ingest`) for the first manual run on the server.
- `/api/config` reports when the data was last refreshed; `/healthz` reports freshness in its body. The map shows "Permits as of <date>", amber after 36 hours, or "Sample data" when running on fixtures.

## Capabilities

### New Capabilities

- `permit-ingest`: how real permit data gets into the lake each day, and what happens when a pull is bad.

### Modified Capabilities

- `permit-api`: `/api/config` and `/healthz` report data freshness.
- `permit-map`: the page shows how fresh the permit data is.

## Impact

- New dependencies: `dagster`, `dagster-dbt`, `dagster-webserver` (runtime, server only).
- New config: `PERMITMAP_SOCRATA_URL` (default `https://cos-data.seattle.gov/resource/76t5-zqzr.csv`).
- New lake tables: `lake.bronze.sdci_building_permits_quarantine`, `lake.bronze.ingest_runs`.
- The first real pull happens on the server, not in the build. Column names are still partly unverified (see design.md, "Risks").

## Out of scope (later changes)

- Docker Compose and deployment (running the Dagster daemon and webserver on the VPS)
- Incremental pulls; a Socrata app token
- Email or push alerts on failure
- Neighborhood spatial join, inspection data and the "under inspection" stage
- Sending engagement events from the page

## Eval questions affected

None. The eval is archived.
