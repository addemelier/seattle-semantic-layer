# Spec Delta: permit-api

## ADDED Requirements

### Requirement: The app picks up the lake when it appears
If the lake does not exist when the app starts, the app SHALL keep serving the page and SHALL start answering permit, freshness and health requests from the lake once it exists, without a restart. Until then, `/api/permits` and `/healthz` SHALL answer 503 and `/api/config` SHALL answer 200 with null freshness. Data written to the lake by another process SHALL be visible to the app's next request.

#### Scenario: First pull finishes after the app started
- **WHEN** the app starts with no lake, and the ingest then builds it
- **THEN** the next `/healthz` returns 200 and `/api/permits` returns the new permits

#### Scenario: Nightly refresh from another container
- **WHEN** a later ingest run in another process adds a permit
- **THEN** the app's next `/api/permits` request includes it
