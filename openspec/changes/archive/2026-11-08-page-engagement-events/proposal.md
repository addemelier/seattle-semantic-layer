# Proposal: page-engagement-events

## Why

v1 (target 2026-11-13) says "engagement events are captured live." The tracking function (`record_event`), the Redis stream and the Parquet drain already exist and are tested, but nothing calls them: the map page sends no events. This change wires the page to them so the PM can see what people search, click and filter.

## What Changes

- `POST /api/events`: the page sends one small JSON event; the server validates it, adds user agent and a salted, daily IP hash, and writes it to the `events:v1` stream through the existing `record_event`.
- The page sends `search`, `permit_click`, `filter_change` and `map_move` events, fire-and-forget, so a slow or missing Redis never affects the map.
- A random session ID kept in the browser, renewed after 30 days idle.
- Browsers signalling Global Privacy Control or Do Not Track send no events.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `engagement-events`: adds how events reach the stream from the map page and what the page sends.

## Impact

- New config: `REDIS_URL` (already read by the drain), `PERMITMAP_TRUST_PROXY` (default off). Uses the existing `EVENT_IP_SALT`.
- Touches `permitmap/app/main.py`, `permitmap/app/config.py`, `static/index.html`, `static/app.js`, `README.md`, which `live-permits-ingest` also edits. Whichever merges second needs a rebase.
- No new dependencies (`redis` and `fakeredis` are already present).

## Out of scope (later changes)

- Running the drain on a schedule (Dagster) and loading events into DuckLake models
- Redis and the app in Docker Compose (deployment change)
- `list_open` events (no list view yet)
- Rate limiting, bot filtering, a cookie banner
- Any dashboard of the events

## Eval questions affected

None. The eval is archived.
