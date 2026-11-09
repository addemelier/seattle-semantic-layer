# Design: deploy-v1

Decisions from the voice design session of 2026-11-05 (saved as "Deployment design notes"), confirmed and extended in text on 2026-11-08. No open questions block building.

## Context

`main` has the map app (`python -m permitmap.app`), the nightly ingest (`python -m permitmap.ingest`, Dagster definitions in `permitmap/orchestration/definitions.py` with the 5:00am schedule) and engagement events (`POST /api/events` → Redis stream `events:v1`). Nothing is containerized. Config comes from env vars: `PERMITMAP_LAKE_CATALOG`, `PERMITMAP_LAKE_DATA`, `PERMITMAP_HOST`, `PERMITMAP_PORT`, `PERMITMAP_STYLE_URL`, `PERMITMAP_GEOCODER_URL`, `PERMITMAP_SOCRATA_URL`, `PERMITMAP_TRUST_PROXY`, `REDIS_URL`, `EVENT_IP_SALT`. `dbt/profiles.yml` reads `PERMITMAP_LAKE_CATALOG`.

Two facts drive this design:
- `connect_lake` records the **absolute** data path in the DuckLake catalog, so every container must mount the lake at the same path.
- The app opens the lake once at startup, and only if the catalog file exists (`_open_lake` in `main.py`). On a fresh server it starts before the first pull and would stay empty until restarted.

The build sandbox reaches PyPI and npm but not Docker Hub, Socrata or any server, so nothing here is verified by building or running containers. Tests check the files' structure, and a PyPI check proves the arm64 wheels exist.

## Goals / Non-Goals

**Goals:** the PM creates a server, points Coolify at the repo, sets one secret and gets a public map with real permits that refreshes every morning, captures events, and redeploys itself on merge.

**Non-goals:** see the proposal's "Out of scope".

## Decisions (PM)

| # | Decision | Reason |
|---|---|---|
| D1 | **Coolify-generated address for v1**, no custom domain. Coolify handles HTTPS. (2026-11-05) | Quickest; a domain can come later. |
| D2 | **Dagster UI private**, reachable only through an SSH tunnel. (2026-11-05) | Nothing exposed, no password to manage; keeps a later move to a Pi or Dagster Cloud open. |
| D3 | **No backups for v1.** Event backups are a later add-on. (2026-11-05) | Simplest. Permit data can be re-pulled. |
| D7 | **Host on a Contabo Cloud VPS 10 in Seattle (x86, 4 vCPU, 8 GB)** instead of a Contabo server. (2026-11-08) | Hetzner's CAX/CX plans have been unorderable since September and its next option is about €20/month; Contabo is about €5, closest to the PM and has double the RAM. The image stays multi-arch, so a later move to a Pi is unchanged. |
| D4 | **Redeploy automatically on every merge to main** (Coolify auto-deploy). (2026-11-05) | Simplest. Accepted risk: a bad merge goes straight live. |
| D5 | **The first real pull runs automatically** when the Dagster daemon starts and the lake has never had an accepted run. (2026-11-08) | Real data minutes after the first deploy, with no terminal step. Replaces the manual first run in the voice notes. |
| D6 | **No scheduled event drain yet.** Events stay in Redis (append-only file on its volume, stream capped at about 1 million entries by `record_event`). (2026-11-08) | Keeps this change to deployment; draining is a later change. |

## Decisions (agent, accepted by the PM with the design)

| # | Decision | Reason |
|---|---|---|
| A1 | **One image** (`Dockerfile`, base `python:3.11-slim-bookworm`, multi-arch) for app, daemon and webserver, with different commands. | One build per deploy; the same code everywhere. |
| A2 | **The lake mounts at `/data/lake`** in all three Python containers (`PERMITMAP_LAKE_CATALOG=/data/lake/catalog.sqlite`, `PERMITMAP_LAKE_DATA=/data/lake/files`). | The catalog records absolute paths (Context). |
| A3 | **Dagster run history in SQLite** under `DAGSTER_HOME=/data/dagster` on volume `dagster_home`; telemetry off. | Matches "no Postgres"; daemon and webserver share it through the volume. |
| A4 | **Dagster webserver port published as `127.0.0.1:3000:3000`.** Tunnel: `ssh -L 3000:127.0.0.1:3000 root@<server-ip>`, then open `http://localhost:3000`. | D2. |
| A5 | **Redis `redis:8-alpine`** with `--appendonly yes`, volume `redis_data`, no published port. | Persistence without exposure. |
| A6 | **App health check hits `/api/config`**, not `/healthz`. | `/healthz` is 503 until the first pull finishes and would fail the first deploy. |
| A7 | **`EVENT_IP_SALT` is required** via `${EVENT_IP_SALT:?set EVENT_IP_SALT in Coolify}`; `PERMITMAP_TRUST_PROXY=1` is set in the Compose file. | Coolify shows `${...}` variables in its UI; the app sits behind Coolify's proxy. |
| A8 | **The app re-tries opening the lake on each request until it opens**, then keeps that connection. | Fixes the fresh-server gap without a restart. |
| A9 | **Bootstrap failures never stop the daemon.** The bootstrap logs and exits 0 whatever happens. | A bad first pull must not leave the schedule off. |
| A10 | **The image runs as a non-root user** (`app`, uid 10001) that owns `/data`. | Basic container hygiene. |
| A11 | **No ports are published for the app**; it `expose`s 8000 and Coolify's proxy routes the generated address to it. | Coolify assigns the address per service in its UI (D1). |

## Build notes (for the builder; decisions already made)

- **Lazy lake (A8), in `permitmap/app/main.py`:** replace direct reads of `app.state.con` with a helper `get_con(app)` that returns `app.state.con` if set, else calls `_open_lake(config)`, stores the result if not None, and returns it. Use it in `freshness()`, `/healthz` and `/api/permits`. Keep `_open_lake`'s rule of never creating a catalog.
- **Cross-process visibility test:** in `tests/test_app_lake.py`, build a temp lake with `load_fixture`, create the app with a `Config` pointing at it, call `/api/permits` once, then in a **separate process** (`subprocess.run([sys.executable, "-c", ...])`) insert one more open permit into `lake.gold.fct_open_permits` inside the test's bbox, then call `/api/permits` again and assert the new permit is there. **Fallback, already decided:** if that assertion fails because the long-lived connection doesn't see the other process's commit, change `get_con` to open a fresh connection per request (close it after the response) and note it in the PR. Do not write BLOCKED.md for this.
- **`Dockerfile`:**
  - `FROM python:3.11-slim-bookworm`; `ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1`.
  - `WORKDIR /app`; copy `pyproject.toml`, `permitmap/`, `dbt/`, `deploy/`; `pip install .` (no dev extras).
  - `RUN python -c "from permitmap.lake import load_extensions; load_extensions()"` so the DuckDB extensions come from the wheels at build time.
  - `RUN dbt deps --project-dir dbt --profiles-dir dbt || true` only if `dbt/packages.yml` exists (skip otherwise), then `RUN dbt parse --project-dir dbt --profiles-dir dbt` so Dagster has `dbt/target/manifest.json`.
  - Create user `app` (uid 10001), `mkdir -p /data/lake /data/dagster` owned by it, `chown -R app /app/dbt` (dbt writes `target/` at runtime), `USER app`.
  - `ENV PERMITMAP_HOST=0.0.0.0 PERMITMAP_PORT=8000 PERMITMAP_LAKE_CATALOG=/data/lake/catalog.sqlite PERMITMAP_LAKE_DATA=/data/lake/files DAGSTER_HOME=/data/dagster`; `EXPOSE 8000`; default `CMD ["python", "-m", "permitmap.app"]`.
- **`.dockerignore`:** `.git`, `data/`, `tests/`, `docs/`, `openspec/`, `.claude/`, `**/__pycache__`, `*.pyc`, `dbt/target/`, `dbt/logs/`, `.venv/`, `.pytest_cache/`, `.env`.
- **`deploy/dagster.yaml`:** `storage: sqlite: base_dir: /data/dagster/storage`, `local_artifact_storage: module: dagster.core.storage.root, class: LocalArtifactStorage, config: base_dir: /data/dagster/artifacts`, `telemetry: enabled: false`, `run_coordinator: module: dagster.core.run_coordinator, class: QueuedRunCoordinator, config: max_concurrent_runs: 1`. Copied into `$DAGSTER_HOME/dagster.yaml` by the entrypoints at start (overwrite each start so config changes ship with deploys).
- **`deploy/workspace.yaml`:** `load_from: [{python_module: permitmap.orchestration.definitions}]`.
- **`deploy/entrypoint-daemon.sh`** (POSIX sh, `set -eu`): copy `dagster.yaml`; `python -m permitmap.deploy.bootstrap`; `exec dagster-daemon run -w /app/deploy/workspace.yaml`.
- **`deploy/entrypoint-webserver.sh`**: copy `dagster.yaml`; `exec dagster-webserver -h 0.0.0.0 -p 3000 -w /app/deploy/workspace.yaml`.
- **`permitmap/deploy/__init__.py`, `permitmap/deploy/bootstrap.py`:** `needs_bootstrap(config) -> bool` is true when the catalog file is missing, or `lake.bronze.ingest_runs` is missing, or it has no row with `status = 'accepted'` (open the lake only if the catalog file exists). `main()`: if not needed, print `bootstrap: accepted run exists, skipping` and return 0; else run `subprocess.run([sys.executable, "-m", "permitmap.ingest"], cwd="/app" or the repo root when not in a container)` and print its outcome; catch every exception; always exit 0 (A9).
- **`permitmap/deploy/check_wheels.py`:** reads `[project].dependencies` from `pyproject.toml` with `tomllib`, then runs `pip install --dry-run --quiet --ignore-installed --only-binary=:all: --platform <plat> --python-version 3.11 --implementation cp --target <tmpdir> <deps...>` for `manylinux_2_28_aarch64` and `manylinux_2_28_x86_64` (`--platform` repeated with the older `manylinux2014_<arch>` tag as well, so either tag matches). Exit 0 only if both succeed; print which platform failed and pip's message otherwise. Usage: `python -m permitmap.deploy.check_wheels`.
- **`docker-compose.yml`** (no `version:` key):
  - `x-permitmap-env` anchor with `PERMITMAP_LAKE_CATALOG`, `PERMITMAP_LAKE_DATA`, `DAGSTER_HOME`, `REDIS_URL: redis://redis:6379/0`, `PERMITMAP_SOCRATA_URL: ${PERMITMAP_SOCRATA_URL:-https://cos-data.seattle.gov/resource/76t5-zqzr.csv}`.
  - `app`: `build: .`, environment = anchor + `EVENT_IP_SALT: ${EVENT_IP_SALT:?set EVENT_IP_SALT in Coolify}` + `PERMITMAP_TRUST_PROXY: "1"`; `expose: ["8000"]`; volume `lake:/data/lake`; `depends_on: [redis]`; `restart: unless-stopped`; healthcheck `["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/config', timeout=3)"]`, interval 30s, timeout 5s, retries 3, start_period 20s.
  - `dagster-daemon`: `build: .`, `command: ["sh", "/app/deploy/entrypoint-daemon.sh"]`, environment = anchor; volumes `lake:/data/lake`, `dagster_home:/data/dagster`; `restart: unless-stopped`.
  - `dagster-webserver`: `build: .`, `command: ["sh", "/app/deploy/entrypoint-webserver.sh"]`, environment = anchor; same two volumes; `ports: ["127.0.0.1:3000:3000"]`; `restart: unless-stopped`.
  - `redis`: `image: redis:8-alpine`, `command: ["redis-server", "--appendonly", "yes"]`, volume `redis_data:/data`, `restart: unless-stopped`, no `ports`.
  - `volumes: lake: {}, redis_data: {}, dagster_home: {}`.
- **Structure tests** in `tests/test_deploy_files.py` with `yaml.safe_load` (PyYAML ships with dbt): exactly the four services; only `dagster-webserver` has `ports` and each starts with `127.0.0.1:`; `redis` and `app` have none; `app` has `expose` 8000 and a healthcheck whose command contains `/api/config`; `EVENT_IP_SALT` in `app` uses the `:?` form; every Python service mounts `lake:/data/lake`; daemon and webserver mount `dagster_home:/data/dagster`; `redis` runs with `--appendonly yes` and mounts `redis_data`; the three volumes are declared; no literal value for `EVENT_IP_SALT` appears anywhere in the repo outside tests. Dockerfile: base image is `python:3.11-slim-bookworm`, has a `USER` line not root, runs `dbt parse`, sets the four `ENV` paths. `deploy/workspace.yaml` loads `permitmap.orchestration.definitions`. `deploy/dagster.yaml` uses sqlite storage under `/data/dagster` and telemetry off. Entry scripts end with `exec dagster-daemon run` / `exec dagster-webserver` and the daemon script runs `permitmap.deploy.bootstrap` first.
- **README "Deploy" section** — the PM's steps, in this order:
  1. Order a Contabo Cloud VPS 10 in US West (Seattle) with Ubuntu 24.04 (about €5.45/month), add your SSH key, then on the server allow ports 22, 80, 443, 8000, 6001 and 6002 with `ufw`.
  2. Install Coolify with its one-line installer from coolify.io, open its dashboard on port 8000 of the server and create the admin account.
  3. In Coolify: add a resource from your GitHub repo using the Docker Compose build pack (`docker-compose.yml`).
  4. Set `EVENT_IP_SALT` in the resource's environment variables to a long random string (`openssl rand -hex 32`).
  5. On the `app` service, use the generated address (HTTPS is automatic); leave the other services without one.
  6. Turn on automatic deployment on push to `main`, then deploy. Within a few minutes the map shows "Permits as of" today.
  7. Dagster UI: `ssh -L 3000:127.0.0.1:3000 root@<server-ip>`, then open `http://localhost:3000`.
  8. If the first pull is rejected, the Dagster daemon log and `lake.bronze.ingest_runs` show the reason (missing columns list what Socrata sent).
  Also note: no backups yet (D3), and moving to a Pi is the same Compose file with the three volumes copied over.

## Risks

- **No container is built or run in the build.** Docker Hub isn't reachable from the builder, so the first real build happens on the server. The structure tests and the arm64 wheel check cover the likely failures; anything else shows up in Coolify's build log on the first deploy.
- **Shared SQLite catalog across containers.** The app reads while the daemon writes, through the same volume on one host, which SQLite's locking supports. The cross-process test covers visibility; a long nightly write could make a request wait briefly.
- **Coolify version details** (variable UI, how ports and the generated address are set) may differ from the README; the Compose file uses only standard Compose features.
- **Auto-deploy (D4)** rebuilds on every merge, including during the 5:00am pull. A redeploy then interrupts that run; the guarded swap keeps yesterday's data, and the next schedule or a manual run from the Dagster UI retries.
