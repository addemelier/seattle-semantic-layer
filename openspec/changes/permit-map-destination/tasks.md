# Tasks: permit-map-destination

Every task runs offline. Read design.md "Facts found" and "Build notes" first.

## 1. Reset docs to the new destination

- [x] 1.1 Move the old docs: `git mv docs/product-brief.md docs/archive/benchmark-product-brief.md` and `git mv docs/eval-questions.md docs/archive/eval-questions.md`. Write a new one-page `docs/product-brief.md` from design.md D1–D22 (sections: what it is, the user, v1 finish line, data, architecture, out of scope). Rewrite `README.md` (what it is in two sentences, status "in development, v1 target 2026-11-13", stack, link to the brief; no results table). In `CLAUDE.md`, apply the "CLAUDE.md replacement text" from design.md exactly, and touch nothing else. In `openspec/config.yaml`, replace the `context:` block with the CLAUDE.md H1 paragraph plus "Read CLAUDE.md for modes and the APPROVED / BLOCKED.md protocol."
  - Verify: `test -f docs/archive/eval-questions.md && test -f docs/archive/benchmark-product-brief.md && ! grep -qi "eval is the product" CLAUDE.md && ! grep -qi "benchmark" openspec/config.yaml && grep -qi "permit" README.md docs/product-brief.md`

## 2. Python package and offline DuckLake

- [ ] 2.1 Create `pyproject.toml` (package `permitmap`, Python ≥3.11) with deps `duckdb==1.5.5`, `duckdb-extensions`, `duckdb-extension-ducklake`, `duckdb-extension-sqlite_scanner` (all pinned to the duckdb version), `dbt-core`, `dbt-duckdb`, `pyarrow`, `redis>=5`, and dev extras `pytest`, `fakeredis`. Create `permitmap/__init__.py` and `permitmap/lake.py` with `connect_lake(catalog_path, data_path) -> duckdb.DuckDBPyConnection`, which imports the extensions offline (see design Facts), attaches DuckLake as `lake` and creates its parent directories. Add `data/` to `.gitignore` (replacing the narrower `data/raw/` and `data/quarantine/` lines). Write `tests/test_lake.py`: in `tmp_path`, create a table in `lake`, reopen the connection and read it back.
  - Verify: `pip install -e '.[dev]' && python -m pytest tests/test_lake.py -q`

## 3. Synthetic fixtures

- [ ] 3.1 Create `tests/fixtures/sdci_building_permits_sample.csv` with ~40 synthetic rows using exactly the column names in design Facts. Include: every closed and known-open status from Build notes; one unknown status (`Pending Something`); two rows sharing a `permitnum`; at least 3 ADU descriptions (ADU, DADU, "accessory dwelling unit"); demolition and new-building types; all coordinates inside lat 47.49–47.74 and lon −122.44 to −122.24. Create `tests/fixtures/neighborhoods_sample.geojson` with 3 rectangular polygons (property `neighborhood_name`: Ballard, Capitol Hill, Beacon Hill). Create `tests/fixtures/README.md` stating that the data is synthetic and the column names are unverified. Write `tests/test_fixtures.py` asserting those properties.
  - Verify: `python -m pytest tests/test_fixtures.py -q`

## 4. dbt project and staging model

- [ ] 4.1 Create `permitmap/load_fixture.py` (`python -m permitmap.load_fixture`): it loads the fixture CSV, all columns as VARCHAR, into `lake.bronze.sdci_building_permits` and replaces the table on rerun. Create the dbt project under `dbt/` (`dbt_project.yml`, `profiles.yml` target `fixture` attaching the DuckLake catalog at `data/lake/catalog.sqlite`, plus `models/staging/_sources.yml`) and `models/staging/stg_sdci__building_permits.sql`: snake_case names, typed dates/numerics, `status_norm = lower(trim(statuscurrent))`, with a `.yml` describing every column. If dbt-duckdb can't attach DuckLake offline, apply the design D19 fallback (a DuckDB file at `data/warehouse.duckdb`) and note it in the PR.
  - Verify: `python -m permitmap.load_fixture && dbt build --project-dir dbt --profiles-dir dbt -s stg_sdci__building_permits`

## 5. Gold open permits and semantic definitions

- [ ] 5.1 Create `dbt/models/gold/fct_open_permits.sql` implementing the open-permits spec (status sets, stage, work_type, dedupe from design Build notes) with exactly the spec's gold columns. Add `dbt/models/gold/fct_open_permits.yml` with a description on every column; `unique` and `not_null` on `permit_id`; `accepted_values` on `stage` and `work_type`; and a `warn`-severity test that fails on statuses outside both sets. Add `dbt/models/gold/semantic_models.yml` with a semantic model over `fct_open_permits` (dimensions stage, work_type, applied_date) and metric `open_permit_count`. Add `tests/test_open_permits.py` that runs against the built lake and checks: no closed statuses present, the duplicate permit appears once, the DADU row is `adu`, and the unknown-status row is present.
  - Verify: `python -m permitmap.load_fixture && dbt build --project-dir dbt --profiles-dir dbt -s +fct_open_permits && dbt parse --project-dir dbt --profiles-dir dbt && python -m pytest tests/test_open_permits.py -q`

## 6. Engagement events to Redis Stream

- [ ] 6.1 Create `permitmap/events.py` with `record_event(r, event_type, session_id, *, search_text=None, lat=None, lon=None, filters=None, permit_id=None, user_agent=None, referrer=None, ip=None, now=None) -> str`. It validates the type, rounds lat/lon to 3 decimals, hashes the IP per the spec using env `EVENT_IP_SALT` (no salt → null hash, IP discarded), `XADD`s to `events:v1` with approximate MAXLEN, and returns the event_id. Write `tests/test_events.py` (fakeredis) covering every engagement-events scenario except the drain, including asserting that the raw IP string appears in no stored field.
  - Verify: `python -m pytest tests/test_events.py -q`

## 7. Drain events to Parquet

- [ ] 7.1 Create `permitmap/drain_events.py` with `drain(r, landing_dir, batch_size=1000) -> int` (events written). It creates consumer group `drainer` if missing, reads with `XREADGROUP`, writes Parquet partitioned by event UTC date at the path in Build notes, and `XACK`s only after the write. Add a `python -m permitmap.drain_events` entry point (Redis URL from env `REDIS_URL`). Write `tests/test_drain_events.py` (fakeredis, `tmp_path`): 10 events → drain → 10 rows; second drain → 0 files written; events on two dates → two partitions; a simulated write failure leaves the events pending (unacked).
  - Verify: `python -m pytest tests/test_drain_events.py -q && python -m pytest -q`
