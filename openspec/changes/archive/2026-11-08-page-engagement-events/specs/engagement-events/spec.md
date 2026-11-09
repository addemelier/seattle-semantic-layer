# Spec Delta: engagement-events

## ADDED Requirements

### Requirement: Event intake endpoint
`POST /api/events` SHALL accept a JSON object with `event_type`, `session_id` and the optional fields `search_text`, `lat`, `lon`, `filters`, `permit_id` and `referrer`, and record it on the event stream. The server SHALL add the user agent from the request and an IP hash per the "Raw IPs are never stored" requirement; the client cannot supply `ip`, `ip_hash`, `user_agent`, `event_id` or `ts`. Responses: 204 when recorded; 400 for an unknown event type, a session ID that is not 32 lowercase hex characters, `search_text` over 200 characters, `permit_id` over 64 characters, `referrer` over 500 characters, `filters` that is not an object with only `stage` and/or `work_type` lists, non-numeric coordinates, or unexpected fields; 413 for a body over 2 KB; 503 when the event store is not configured or unreachable, within about one second.

#### Scenario: Valid event
- **WHEN** the page posts `{"event_type": "permit_click", "session_id": "<32 hex>", "permit_id": "6999001-CN"}`
- **THEN** the response is 204 and one entry appears on `events:v1` with that permit id and the request's user agent

#### Scenario: Client tries to set the IP
- **WHEN** a posted event includes an `ip` field
- **THEN** the response is 400 and nothing is written

#### Scenario: Store down
- **WHEN** Redis is unreachable
- **THEN** the response is 503 within about one second

### Requirement: The map page sends engagement events
Unless the browser signals Global Privacy Control or Do Not Track, the page SHALL send: `search` when an address search is submitted (`search_text` as typed, plus the matched point's coordinates when the search succeeded); `permit_click` when a pin is clicked (`permit_id` and the pin's coordinates); `filter_change` when any filter box changes (`filters` with the checked `stage` and `work_type` values); and `map_move` when the map settles at zoom 12 or closer (the map center), at most once per 2 seconds. Sending SHALL never delay or break the map: failures are ignored and nothing waits on the response.

#### Scenario: Pin click
- **WHEN** a user clicks a permit pin
- **THEN** one `permit_click` event with that permit's id is sent

#### Scenario: Failed search
- **WHEN** a search returns "Address not found in Seattle"
- **THEN** a `search` event with the typed text and no coordinates is sent

#### Scenario: Privacy signal
- **WHEN** the browser reports Global Privacy Control or Do Not Track
- **THEN** the page sends no events

#### Scenario: Event store down
- **WHEN** `/api/events` returns 503
- **THEN** the map, search, filters and detail panel all keep working with no visible error

### Requirement: Browser session ID
The page SHALL identify a browser with a random 32-hex-character session ID stored in the browser and reused across visits, and SHALL replace it with a new one when it has not been used for 30 days. If browser storage is unavailable, the page SHALL use an ID that lasts for the page load. The ID SHALL contain nothing derived from the user or device.

#### Scenario: Returning visitor
- **WHEN** a user reloads the page 3 days after their last visit
- **THEN** events carry the same session ID as before

#### Scenario: Long gap
- **WHEN** a user returns 31 days after their last visit
- **THEN** events carry a new session ID
