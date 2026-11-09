# permit-ingest Specification

## Purpose
How real SDCI permit data gets into the lake every day, and what happens when a pull is bad.

## Requirements

### Requirement: Daily full snapshot
The system SHALL pull the full SDCI building-permits dataset from the configured Socrata CSV endpoint once a day at 5:00am America/Los_Angeles, page by page until a short page is returned, and SHALL rebuild silver and gold from it. The same pipeline SHALL be runnable once on demand from the command line. Running it twice on the same source data SHALL leave the lake in the same state (idempotent).

#### Scenario: Multi-page pull
- **WHEN** the source returns two full pages and then a short page
- **THEN** every row from all three pages is loaded, and no further page is requested

#### Scenario: Rerun
- **WHEN** the pipeline runs twice against identical source data
- **THEN** bronze, quarantine and gold row counts are the same after both runs

### Requirement: A bad pull never replaces good data
A pull SHALL be loaded to a side table and swapped into `lake.bronze.sdci_building_permits` only if (a) every column the staging model reads is present and (b) the number of valid rows is at least 90% of the last accepted load. On the first ever run only check (a) applies. If any page fails after retries, or either check fails, the run SHALL be rejected, bronze and gold SHALL be left unchanged, and the run SHALL end in failure.

#### Scenario: Missing column
- **WHEN** the pulled data has no `statuscurrent` column
- **THEN** the run is rejected, the reason names each missing column and lists the columns that were present, and the map still shows the previous data

#### Scenario: Shrunk pull
- **WHEN** the last accepted load had 1,000 valid rows and today's pull has 850
- **THEN** the run is rejected with a reason naming both counts

#### Scenario: Normal shrink
- **WHEN** the last accepted load had 1,000 valid rows and today's pull has 950
- **THEN** the run is accepted and bronze holds the 950 rows

#### Scenario: Source down
- **WHEN** a page request keeps failing after retries
- **THEN** the run is rejected and nothing is swapped

### Requirement: Malformed rows are quarantined
Rows with a blank permit number, or with a latitude or longitude that is present but not a number, SHALL NOT be loaded into bronze. They SHALL be written to `lake.bronze.sdci_building_permits_quarantine` with the run id and a reason. Quarantined rows do not count as valid rows. The quarantine table SHALL hold the latest accepted run's rows.

#### Scenario: Blank permit number
- **WHEN** a pulled row has an empty `permitnum`
- **THEN** it appears in the quarantine table with reason `blank_permitnum` and not in bronze

#### Scenario: Bad coordinates
- **WHEN** a pulled row has latitude `n/a`
- **THEN** it appears in the quarantine table with reason `bad_coordinates`

### Requirement: Every run is logged
Every run, accepted or rejected, SHALL append one row to `lake.bronze.ingest_runs` with: run id, start and finish time (UTC), rows fetched, valid rows, rows quarantined, status (`accepted` or `rejected`) and reason (null when accepted).

#### Scenario: Rejected run logged
- **WHEN** a run is rejected for shrinking
- **THEN** `ingest_runs` gains a row with status `rejected` and the shrink reason
