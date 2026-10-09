# engagement-events Specification

## Purpose
TBD - created by archiving change permit-map-destination. Update Purpose after archive.

## Requirements

### Requirement: Anonymous event capture
The system SHALL record user interactions as anonymous events with no login. Allowed event types: `search`, `permit_click`, `filter_change`, `map_move`, `list_open`. Each event carries: event_id, UTC timestamp, event_type, session_id (random, client-generated), and, when applicable: search_text, map latitude/longitude rounded to 3 decimals (~100 m), filters (JSON), permit_id, user_agent, referrer, ip_hash.

#### Scenario: Unknown event type rejected
- **WHEN** an event with type `purchase` is recorded
- **THEN** it is rejected with an error and nothing is written

#### Scenario: Map position is coarsened
- **WHEN** an event is recorded at latitude 47.668123
- **THEN** the stored latitude is 47.668

### Requirement: Raw IPs are never stored
The system SHALL NOT store a raw IP address anywhere. If an IP is provided, only a SHA-256 hash of (secret salt + UTC date + IP) is stored. The same visitor therefore hashes identically within a day and differently across days.

#### Scenario: Same IP, same day
- **WHEN** two events from the same IP are recorded on the same UTC date
- **THEN** their ip_hash values are equal and neither event contains the IP string

#### Scenario: Same IP, next day
- **WHEN** events from the same IP are recorded on different UTC dates
- **THEN** their ip_hash values differ

### Requirement: Events drain to the landing zone
Events SHALL be written live to a stream, then moved by a drain step to Parquet files partitioned by event date. An event is acknowledged only after its Parquet file is written, so a crash re-delivers events rather than losing them. Running the drain again with nothing pending writes no files.

#### Scenario: Drain twice
- **WHEN** 10 events are recorded and the drain runs twice
- **THEN** exactly 10 events exist across the Parquet files and the second run writes nothing

### Requirement: Event data stays out of the repository
Event data SHALL never be committed to the public repository.

#### Scenario: Landing path is ignored
- **WHEN** the drain writes under `data/`
- **THEN** git ignores those files
