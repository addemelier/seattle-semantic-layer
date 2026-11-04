# Spec Delta: permit-map

## ADDED Requirements

### Requirement: Data freshness label
The page SHALL show how fresh the permit data is, in a small label that does not cover the map controls: "Permits as of <Mon D>" (the `data_as_of` date in America/Los_Angeles) when the data is fresh; the same text in amber with ", may be out of date" appended when `data_fresh` is false; and "Sample data" when `data_as_of` is null.

#### Scenario: Fresh
- **WHEN** `/api/config` returns `data_as_of` 2026-11-03T13:05:00Z and `data_fresh: true`
- **THEN** the label reads "Permits as of Nov 3"

#### Scenario: Stale
- **WHEN** `/api/config` returns `data_fresh: false`
- **THEN** the label is amber and ends with ", may be out of date"

#### Scenario: Fixtures
- **WHEN** `/api/config` returns `data_as_of: null`
- **THEN** the label reads "Sample data"
