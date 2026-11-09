# Proposal: deploy-v1

## Why

Everything v1 needs is built and merged: the map, the nightly ingest with freshness, and engagement events. It all still runs only on a laptop with sample data. v1 (target 2026-11-13) is "the PM sends a friend a URL." This change packages the stack so Coolify on one Contabo server (Seattle) can run it, pull real permits on its own, and redeploy on every merge.

## What Changes

- One `Dockerfile` (one image, multi-arch) and one `docker-compose.yml` with four services: `app` (FastAPI map), `redis` (Redis 8, event stream), `dagster-daemon` (runs the 5:00am schedule) and `dagster-webserver` (run history, private).
- Named volumes so the lake, Redis data and Dagster run history survive redeploys.
- On a fresh server, the first real permit pull runs automatically when the Dagster daemon starts.
- The app picks up the lake once it exists, instead of needing a restart after the first pull.
- A Dagster instance config that keeps run history in SQLite on its volume (no Postgres).
- A check that every Python dependency installs on arm64 from wheels.
- A "Deploy" section in the README with the PM's manual Contabo and Coolify steps and the SSH-tunnel command for the Dagster UI.

## Capabilities

### New Capabilities

- `deployment`: how the stack is packaged, what persists, what's exposed and how it starts on a fresh server.

### Modified Capabilities

- `permit-api`: the app starts serving permits once the lake appears, without a restart.

## Impact

- New files: `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `deploy/dagster.yaml`, `deploy/workspace.yaml`, `deploy/entrypoint-daemon.sh`, `permitmap/deploy/` (bootstrap and wheel check).
- Small change to `permitmap/app/main.py`.
- Secrets live only in Coolify: `EVENT_IP_SALT` is required.
- Manual PM steps (builders never touch hosting accounts): create the Contabo server, install Coolify, add the repo, set the secret, assign the address, turn on auto-deploy.

## Out of scope (later changes)

- Custom domain; backups of any volume (events backup noted as an add-on)
- Draining events from Redis to Parquet on a schedule
- Raspberry Pi migration, Dagster Cloud
- Redis response caching, rate limiting, CI pipelines

## Eval questions affected

None. The eval is archived.
