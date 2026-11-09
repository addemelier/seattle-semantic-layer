# Spec Delta: permit-api

## MODIFIED Requirements

### Requirement: Map configuration and health
`GET /api/config` SHALL return `{style_url, data_as_of, data_fresh}`. `style_url` is the basemap style URL, taken from configuration with the OpenFreeMap Positron style as the default. `data_as_of` is the finish time (UTC, ISO 8601) of the most recent accepted ingest run, or `null` when there has never been one (fixture data). `data_fresh` is `true` when `data_as_of` is within the last 36 hours, `false` when it is older, and `null` when `data_as_of` is `null`. `GET /healthz` SHALL return 200 `{"status": "ok", "data_as_of": ..., "data_fresh": ...}` when the app can read the gold table, even when the data is stale, and 503 otherwise.

#### Scenario: Default style
- **WHEN** no style is configured
- **THEN** `/api/config` returns `https://tiles.openfreemap.org/styles/positron`

#### Scenario: Fixture data
- **WHEN** the lake was built from fixtures and has no accepted ingest run
- **THEN** `/api/config` returns `data_as_of: null` and `data_fresh: null`

#### Scenario: Stale data stays healthy
- **WHEN** the last accepted ingest run finished 40 hours ago
- **THEN** `/api/config` returns `data_fresh: false`, and `/healthz` returns 200 with `data_fresh: false`
