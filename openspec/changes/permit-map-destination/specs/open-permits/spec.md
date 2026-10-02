## ADDED Requirements

### Requirement: Open permit definition
A permit SHALL be "open" unless its current status is one of the closed statuses: expired, completed/finaled, closed, canceled/cancelled or withdrawn (matched case-insensitively, ignoring surrounding whitespace). Applied, in-review, issued and inspection-in-progress permits are open.

#### Scenario: Issued permit is open
- **WHEN** a permit has status "Issued"
- **THEN** it appears in the gold open-permits table

#### Scenario: Finaled permit is excluded
- **WHEN** a permit has status "Completed", "Expired", "Closed", "Canceled", "Cancelled" or "Withdrawn"
- **THEN** it does not appear in the gold open-permits table

#### Scenario: Unknown status is kept and surfaced
- **WHEN** a permit has a status that is in neither the closed set nor the known-open set
- **THEN** it is treated as open, and a warning-severity data test reports the unknown status value

### Requirement: Stage
Every open permit SHALL have exactly one `stage`: `in_review` when it has no issued date, and `issued` when it has one.

#### Scenario: Not yet issued
- **WHEN** an open permit has an applied date and no issued date
- **THEN** its stage is `in_review`

### Requirement: Work type
Every open permit SHALL have exactly one `work_type` from `new_building`, `addition_alteration`, `demolition`, `adu`. ADU is detected from the description ("ADU", "AADU", "DADU", "accessory dwelling") and takes precedence over every other type. Demolition and new building come from the permit type. Everything else is `addition_alteration`.

#### Scenario: Detached ADU described in free text
- **WHEN** a permit's type is "New" and its description contains "DADU"
- **THEN** its work_type is `adu`

### Requirement: Gold fields
The gold open-permits table SHALL expose one row per permit with: permit_id (unique, not null), address, description, work_type, stage, status_raw, applied_date, issued_date, expires_date, valuation_usd, housing_units_added, housing_units_removed, contractor, permit_url, latitude, longitude. Every column SHALL have a description.

#### Scenario: Duplicate source rows
- **WHEN** the source contains two rows with the same permit number
- **THEN** the gold table contains one row for that permit (the most recently applied record)

### Requirement: Semantic definitions are declared
The open-permit count, stage and work_type SHALL be declared in a semantic-model file so the definitions live in one place that both the app and documentation reference.

#### Scenario: Definitions parse
- **WHEN** the dbt project is parsed
- **THEN** the semantic model and its `open_permit_count` metric parse without error
