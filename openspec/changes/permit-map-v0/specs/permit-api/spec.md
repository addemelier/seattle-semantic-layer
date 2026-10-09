# Spec Delta: permit-api

## Purpose

The HTTP contract for reading open permits by map area and turning a Seattle address into a point. The map page uses it; nothing else may assume more than what is written here.

## ADDED Requirements

### Requirement: Permits in a bounding box
`GET /api/permits?bbox=<min_lon>,<min_lat>,<max_lon>,<max_lat>` SHALL return a GeoJSON FeatureCollection of open permits whose coordinates fall inside the box (edges inclusive). Each feature SHALL be a Point at the permit's longitude/latitude, with every gold open-permits field except latitude and longitude as properties. Permits with no coordinates are never returned.

#### Scenario: Box around fixture permits
- **WHEN** the bbox contains some fixture permits and excludes others
- **THEN** exactly the permits inside the box are returned, each as a Point feature with `permit_id`, `stage`, `work_type` and the other gold fields as properties

#### Scenario: Closed permits never appear
- **WHEN** the bbox covers all of Seattle
- **THEN** no returned feature has a closed status

### Requirement: Malformed bounding box is rejected
The permits endpoint SHALL respond 400 with a JSON error message when `bbox` is missing, does not have four numbers, has min greater than max, or lies outside longitude −180..180 / latitude −90..90.

#### Scenario: Three numbers
- **WHEN** `bbox=-122.4,47.5,-122.3`
- **THEN** the response is 400 and names the bbox as the problem

### Requirement: Stage and work-type filters
The permits endpoint SHALL accept optional `stage` and `work_type` parameters, each a comma-separated list of allowed values (`in_review`, `issued`; `new_building`, `addition_alteration`, `demolition`, `adu`). When present, only permits matching one of the listed values are returned. An omitted parameter means no filter on that field. An unknown value is a 400. An empty value (`stage=`) returns no permits.

#### Scenario: Only ADUs
- **WHEN** `work_type=adu`
- **THEN** every returned feature has `work_type` = `adu`

#### Scenario: Unknown stage
- **WHEN** `stage=finaled`
- **THEN** the response is 400

### Requirement: Result cap
The permits endpoint SHALL return at most 2,000 features, ordered by `applied_date` descending (most recent first, missing dates last), and SHALL include a top-level boolean `truncated` that is true only when more permits matched than were returned.

#### Scenario: Under the cap
- **WHEN** fewer than 2,000 permits match
- **THEN** all are returned and `truncated` is false

### Requirement: Address geocoding
`GET /api/geocode?q=<address>` SHALL return `{lat, lon, matched_address, score}` for the best candidate from the City of Seattle address locator, coordinates in WGS84. The query SHALL be 3–200 characters after trimming (else 400). If the best candidate scores below 80 or there are none, the response SHALL be 404 with a message. If the locator errors, returns malformed data, or takes longer than 5 seconds, the response SHALL be 502 with a message. The locator URL SHALL be configurable.

#### Scenario: Good match
- **WHEN** the locator returns a candidate with score 100 at a Seattle point
- **THEN** the response is 200 with that point and matched address

#### Scenario: Weak match
- **WHEN** the locator's best candidate scores 62
- **THEN** the response is 404

#### Scenario: Locator down
- **WHEN** the locator times out
- **THEN** the response is 502 within about 5 seconds

### Requirement: Map configuration and health
`GET /api/config` SHALL return `{style_url}`, the basemap style URL, taken from configuration with the OpenFreeMap Positron style as the default. `GET /healthz` SHALL return 200 `{"status": "ok"}` when the app can read the gold table, and 503 otherwise.

#### Scenario: Default style
- **WHEN** no style is configured
- **THEN** `/api/config` returns `https://tiles.openfreemap.org/styles/positron`
