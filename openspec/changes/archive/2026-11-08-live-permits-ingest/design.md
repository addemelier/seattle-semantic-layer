# Design: live-permits-ingest

Design session 2026-11-03 (evening). No open questions block building.

## Context

`python -m permitmap.load_fixture` replaces `lake.bronze.sdci_building_permits` with the synthetic CSV, every column VARCHAR. dbt builds `stg_sdci__building_permits` and `fct_open_permits` from it. The app reads gold through one DuckLake connection opened at startup. The build sandbox can reach PyPI but not Socrata, so every test mocks the HTTP call.

The fixture's column names were written from memory. On 2026-11-03 a third-party scraper listing (not the city) showed the dataset at `cos-data.seattle.gov/resource/76t5-zqzr` with `permitnum`, `permitclass`, `permitclassmapped`, `permittypemapped`, `permittypedesc`, `description`, `statuscurrent`, `originaladdress1`, `originalcity`, `originalstate`, `originalzip`, `latitude`, `longitude` and `link`, matching the fixture. The date columns, `estprojectcost`, `contractorcompanyname` and `housingunitsadded/removed` were not shown, so they remain unverified.

## Goals / Non-Goals

**Goals:** real permits on the map every morning with no manual step; a bad night never blanks or shrinks the map; the user can see how fresh the data is.

**Non-goals:** see the proposal's "Out of scope". In particular, running the Dagster daemon on the VPS belongs to the deployment change.

## Decisions (PM, 2026-11-03)

| # | Decision | Reason |
|---|---|---|
| D1 | **Full snapshot every night**, replacing bronze. No incremental merge, no server-side status filter. | Simplest and self-healing. Bronze stays the raw source, so a new closed-status label can't slip past the gold logic. |
| D2 | **Reject a pull** when any column staging reads is missing, or valid rows fall more than 10% below the last accepted load. First run: column check only. A rejected run leaves yesterday's data up. | Catches truncated pulls and renamed columns without blocking ordinary city cleanups. |
| D3 | **Freshness is shown on the map**: "Permits as of Nov 3", amber after 36 hours, "Sample data" on fixtures. `/healthz` reports it too. No email or accounts. | He'll notice while using it, with no credentials to manage. |

## Decisions (agent, accepted by the PM with the design)

| # | Decision | Reason |
|---|---|---|
| A1 | **Pull CSV, not JSON**, from `PERMITMAP_SOCRATA_URL` (default `https://cos-data.seattle.gov/resource/76t5-zqzr.csv`). | CSV flattens the `link` URL object and loads with the same `all_varchar` path as the fixture. |
| A2 | **`/healthz` stays 200 when data is stale** and reports it in the body. | If health failed, Coolify could pull the container and stale data would become no map. |
| A3 | **Schedule 5:00am America/Los_Angeles** (`0 5 * * *`). | Fresh before he looks in the morning; off-peak for the city's servers. |
| A4 | **No Socrata app token.** | Unauthenticated access is enough for one pull a day, and it keeps credentials out of the repo. |
| A5 | **Rows with blank coordinates are kept**; only non-numeric coordinates are quarantined. | A permit with no location is valid source data; the API's bbox filter already skips it. |
| A6 | **Dagster wraps the same functions the CLI calls.** One asset does pull, check and swap; dbt models are `dagster-dbt` assets downstream of it. | One code path to test; the CLI covers the first manual run on the server before Compose exists. |
| A7 | **Freshness label sits bottom-left**, above MapLibre's attribution. | Out of the way of search (top), filters and the detail panel. |

## Build notes (for the builder; decisions already made)

- **Required columns** (the staging model's inputs, in `permitmap/ingest/columns.py` as `REQUIRED_COLUMNS`): `permitnum, permitclass, permitclassmapped, permittypemapped, permittypedesc, description, housingunitsremoved, housingunitsadded, estprojectcost, applieddate, issueddate, expiresdate, completeddate, statuscurrent, originaladdress1, originalcity, originalstate, originalzip, contractorcompanyname, link, latitude, longitude`. Add a test that every column referenced in `dbt/models/staging/stg_sdci__building_permits.sql` is in this list, so the two can't drift.
- **Paging:** `GET <url>?$order=:id&$limit=50000&$offset=<n>`. Stop when a page has fewer data rows than the limit. `httpx`, 60-second timeout, 3 attempts per page with 2, 4 and 8 second waits (make the wait injectable so tests don't sleep). Write each page to a temp directory as `page-0000.csv`, `page-0001.csv`, …
- **Loading:** `read_csv(<paths>, header = true, all_varchar = true, union_by_name = true)` into `lake.bronze.sdci_building_permits__incoming`. Column names compared lower-cased and trimmed.
- **Quarantine rule:** reason `blank_permitnum` when `trim(coalesce(permitnum, '')) = ''`; else `bad_coordinates` when latitude or longitude is non-blank and `try_cast(... AS DOUBLE)` is null. Quarantine columns: all source columns, plus `run_id`, `quarantine_reason`.
- **Swap:** inside one transaction: `CREATE OR REPLACE TABLE lake.bronze.sdci_building_permits AS SELECT <valid rows>` from incoming, `CREATE OR REPLACE` the quarantine table, then drop incoming. On rejection, drop incoming and leave both tables untouched.
- **`lake.bronze.ingest_runs`** columns: `run_id VARCHAR` (uuid4), `started_at TIMESTAMP`, `finished_at TIMESTAMP` (both UTC), `rows_fetched BIGINT`, `rows_valid BIGINT`, `rows_quarantined BIGINT`, `status VARCHAR`, `reason VARCHAR`. Created if missing. The shrink baseline is `rows_valid` of the most recent `accepted` row.
- **Rejection reasons** (exact text the tests check): `missing columns: <a, b>; present: <x, y, …>`, `shrink: <valid> valid rows vs <baseline> last accepted (min <ceil(0.9*baseline)>)`, `fetch failed: <error>`.
- **Pipeline function:** `permitmap/ingest/pipeline.py: run_ingest(config, client=None) -> RunResult` does fetch → load/check → swap → log, raising `IngestRejected` after logging a rejection. `python -m permitmap.ingest` calls it, then runs `dbt build --project-dir dbt --profiles-dir dbt -s +fct_open_permits` through `dbt.cli.main.dbtRunner`, exits 1 on rejection or dbt failure and prints the run summary.
- **Fixture loader stays as is.** It writes no `ingest_runs` row, which is how the app knows it's on sample data.
- **Freshness in the app:** read `max(finished_at) WHERE status = 'accepted'` from `lake.bronze.ingest_runs` per request (cheap; table may not exist → treat as null). The 36-hour threshold is a constant `STALE_AFTER_HOURS = 36` in `permitmap/app/config.py`. Inject "now" in tests.
- **Ingest test fixtures:** build mock pages in tests from `tests/fixtures/sdci_building_permits_sample.csv` (split into pages with a small injected page size); add rows with a blank `permitnum` and with latitude `n/a` inside the test, not in the shared fixture. No new committed data files needed.
- **Dagster:** `permitmap/orchestration/definitions.py` exporting `defs`. Asset `bronze_sdci_building_permits` calls `run_ingest`; `@dbt_assets` from the dbt manifest (generate it with `dbt parse` in the verification command); the dbt source `bronze.sdci_building_permits` maps to that asset key so dbt runs after it. Job `daily_permits_refresh`, schedule `daily_permits_refresh_schedule` with `cron_schedule="0 5 * * *"`, `execution_timezone="America/Los_Angeles"`, default status RUNNING. Pin `dagster`, `dagster-dbt` and `dagster-webserver` to the exact versions pip resolves at build time, and say which in the PR.

## Risks

- **Unverified column names.** If the first server run is rejected for missing columns, the reason lists what Socrata actually sent. The fix is a rename in `stg_sdci__building_permits.sql` and `REQUIRED_COLUMNS`, a small follow-up change.
- **Domain.** The `cos-data.seattle.gov` host comes from a secondary source. It's configurable, so a wrong default is an env-var fix.
- **Gold is rebuilt after bronze is swapped.** If dbt fails, bronze holds new data and gold the previous build. The map keeps working on yesterday's gold, which is acceptable.
