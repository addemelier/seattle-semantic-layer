# Proposal: permit-map-v0

## Why

The gold table of open permits exists, but nobody can see it. v1 (2026-11-13) is "the PM sends a friend a URL, they search an address, see open permits on a map, click one and get details." This change builds that experience end to end on the fixture data, so the remaining v1 work is real data and deployment, not product.

## What Changes

- A small web app (`permitmap/app/`) that serves a map page and a JSON API over `lake.gold.fct_open_permits`.
- `GET /api/permits`: open permits inside a map bounding box as GeoJSON, filterable by stage and work type, capped at 2,000 with a `truncated` flag.
- `GET /api/geocode`: turns a typed Seattle address into a point using the City of Seattle's public address locator.
- `GET /api/config` (basemap style URL) and `GET /healthz`.
- A map page: pins colored by stage with a legend, a zoom-in gate, a permit detail panel (bottom sheet on phones), stage and work-type filters, address search that flies to the address with a 1,000 ft ring, and the current view kept in the URL so a link reopens the same view.
- Headless-browser smoke tests that run fully offline.

## Capabilities

### New Capabilities

- `permit-map`: what the map page shows and how a user searches, filters and opens a permit.
- `permit-api`: the HTTP contract the page (and anything else) uses to read permits and geocode addresses.

### Modified Capabilities

None. `open-permits` is read, not changed.

## Impact

- New runtime deps: `fastapi`, `uvicorn`, `httpx`. New dev deps: `playwright`, `respx` (or httpx `MockTransport`).
- MapLibre GL JS 4.7.1 committed under `permitmap/app/static/vendor/` (from the npm registry).
- Runtime (server only) calls two third parties: OpenFreeMap tiles in the browser and the City of Seattle geocoder from the API. Neither is called at build time.

## Out of scope (later changes)

- List view sorted by distance; minimum-valuation and applied-within filters
- Sending engagement events from the page (the `record_event` function exists; wiring is a later change)
- Live Socrata ingest, Dagster, neighborhood spatial join, "under inspection" stage
- API response caching in Redis; Docker Compose and deployment
- Accounts, watchlists, alerts

## Eval questions affected

None. The eval is archived.
