# Spec Delta: deployment

## Purpose

How the permit map runs on one server: what is packaged, what persists across redeploys, what is reachable from the internet, and how a fresh server gets real data.

## ADDED Requirements

### Requirement: One Compose file runs the whole stack
The repository SHALL contain one Compose file that runs four services from images that build on both arm64 and amd64: the map app, Redis 8, the Dagster daemon and the Dagster webserver. The app, daemon and webserver SHALL use one image built from the repository. Every Python dependency SHALL install on linux arm64 and amd64 from published wheels.

#### Scenario: ARM server
- **WHEN** the stack is built on an ARM server, such as a later Raspberry Pi
- **THEN** every Python dependency installs from a wheel, with nothing compiled from source

### Requirement: Data survives redeploys
The lake (catalog and data files), Redis's data and Dagster's run history SHALL each live in a named volume on the server's disk. The app, daemon and webserver SHALL mount the lake at the same path, so file paths recorded in the catalog resolve in every container. Redis SHALL persist its data to disk (append-only file).

#### Scenario: Redeploy after a merge
- **WHEN** Coolify rebuilds and restarts every container after a merge to main
- **THEN** the map shows the same permits as before, queued events are still in Redis, and Dagster's run history is intact

### Requirement: Only the map is public
Only the app service SHALL be reachable through the server's public proxy. The Dagster webserver SHALL be published only on the server's loopback interface (127.0.0.1), so it is reachable through an SSH tunnel and not from the internet. Redis SHALL NOT publish any port.

#### Scenario: Stranger tries the Dagster UI
- **WHEN** someone on the internet requests the server's Dagster port
- **THEN** the connection is refused

### Requirement: Secrets are never committed
No secret SHALL be committed to the repository. `EVENT_IP_SALT` SHALL be supplied by the host's environment, and the app service SHALL refuse to start without it. The app SHALL trust the proxy's forwarded client IP in this deployment.

#### Scenario: Salt missing
- **WHEN** the stack is started without `EVENT_IP_SALT` set
- **THEN** Compose refuses to start the app and names the missing variable

### Requirement: A fresh server gets real data on its own
When the Dagster daemon starts and the lake has never had an accepted ingest run, the system SHALL run one ingest (pull, checks, swap, dbt) before starting the schedule. If that pull is rejected or fails, the daemon SHALL still start, and the 5:00am schedule SHALL try again. When an accepted run exists, startup SHALL NOT pull.

#### Scenario: First deploy
- **WHEN** the stack starts on a new server with empty volumes and Socrata is reachable
- **THEN** within minutes the map shows real permits and "Permits as of" today's date, with no manual step

#### Scenario: Later restarts
- **WHEN** the daemon restarts on a server that already has an accepted ingest run
- **THEN** no pull runs at startup

#### Scenario: First pull rejected
- **WHEN** the first pull is rejected for missing columns
- **THEN** the daemon still starts and the rejection is in `ingest_runs`

### Requirement: The app is checked for liveness without depending on data
The app container's health check SHALL use an endpoint that answers 200 whenever the web process is up, even before any permit data exists, so a first deploy is not marked unhealthy while the first pull runs.

#### Scenario: First deploy before data
- **WHEN** the app has started but the first pull hasn't finished
- **THEN** the container is healthy and `/healthz` returns 503
