# Tasks: live-permits-ingest

Every task runs offline; tests mock every HTTP call. Read design.md "Decisions" and "Build notes" first. In the build sandbox, export `PW_CHROMIUM_PATH=/opt/pw-browsers/chromium` before UI tests. Never run `playwright install`.

## 1. Socrata fetch

- [x] 1.1 Create `permitmap/ingest/__init__.py`, `permitmap/ingest/columns.py` (`REQUIRED_COLUMNS`, Build notes) and `permitmap/ingest/socrata.py` with `fetch_pages(client, url, out_dir, page_size=50000, sleep=time.sleep) -> list[Path]` (paging, retries and timeout per Build notes; raises `FetchFailed` after the third failed attempt). Add `socrata_url` (env `PERMITMAP_SOCRATA_URL`, default in A1) to `permitmap/app/config.py`. Write `tests/test_ingest_fetch.py` with `respx`: three pages (full, full, short) at page size 3 → three files and exactly three requests carrying `$order=:id`, `$limit=3` and offsets 0/3/6; a page that fails twice then succeeds → success with two recorded sleeps; a page that fails three times → `FetchFailed`. Write `tests/test_ingest_columns.py`: every source column referenced in `dbt/models/staging/stg_sdci__building_permits.sql` is in `REQUIRED_COLUMNS`.
  - Verify: `pip install -e '.[dev]' && python -m pytest tests/test_ingest_fetch.py tests/test_ingest_columns.py -q`

## 2. Guarded bronze load

- [x] 2.1 Create `permitmap/ingest/load.py` with `load_snapshot(con, csv_paths, run_id) -> LoadOutcome`: load to `lake.bronze.sdci_building_permits__incoming`, column check, quarantine split, shrink check against `lake.bronze.ingest_runs`, transactional swap or rollback, exactly as in Build notes (table names, reasons and their exact text). Create `ingest_runs` if missing. Write `tests/test_ingest_load.py` on a temp lake: first run with the fixture CSV is accepted with no baseline; a CSV missing `statuscurrent` is rejected with the exact reason and bronze unchanged; baseline 1,000 → 850 rejected, → 950 accepted (generate rows in the test); a row with blank `permitnum` and one with latitude `n/a` land in quarantine with the right reasons and not in bronze; running the same input twice gives identical bronze and quarantine counts.
  - Verify: `python -m pytest tests/test_ingest_load.py -q`

## 3. One-shot pipeline and CLI

- [x] 3.1 Create `permitmap/ingest/pipeline.py` (`run_ingest`, `RunResult`, `IngestRejected`; logs every run to `ingest_runs` per Build notes) and `permitmap/ingest/__main__.py` (runs the pipeline then dbt via `dbtRunner`, exit codes per Build notes). Write `tests/test_ingest_pipeline.py` with `respx` serving the fixture CSV as pages on a temp lake: a run ends with `ingest_runs` holding one `accepted` row and `lake.gold.fct_open_permits` having the same row count as after `load_fixture`; a follow-up run whose mock returns a 500 on every attempt is logged `rejected` with a `fetch failed:` reason and leaves gold's row count unchanged; the CLI returns exit code 1 in that case.
  - Verify: `python -m permitmap.load_fixture && dbt build --project-dir dbt --profiles-dir dbt -s +fct_open_permits && python -m pytest tests/test_ingest_pipeline.py -q`

## 4. Dagster job and schedule

- [x] 4.1 Add `dagster`, `dagster-dbt`, `dagster-webserver` to `pyproject.toml` (exact versions, Build notes). Create `permitmap/orchestration/__init__.py` and `permitmap/orchestration/definitions.py` (asset, dbt assets, job, schedule per Build notes). Write `tests/test_orchestration.py`: `defs` loads; the schedule has cron `0 5 * * *` in `America/Los_Angeles`; the job contains the bronze asset and `fct_open_permits`, with the bronze asset upstream; materializing the job with the HTTP call mocked (fixture pages) succeeds and writes an `accepted` row to `ingest_runs` on a temp lake.
  - Verify: `pip install -e '.[dev]' && dbt parse --project-dir dbt --profiles-dir dbt && dagster definitions validate -m permitmap.orchestration.definitions && python -m pytest tests/test_orchestration.py -q`

## 5. Freshness in the API

- [x] 5.1 Create `permitmap/app/freshness.py` (`data_freshness(cursor, now) -> (data_as_of, data_fresh)`, Build notes) and extend `/api/config` and `/healthz` in `permitmap/app/main.py` per the `permit-api` delta. Write `tests/test_api_freshness.py`: fixture lake → `data_as_of` and `data_fresh` null and `/healthz` 200; an `accepted` run 2 hours before the injected now → `data_fresh: true` and the ISO timestamp; one 40 hours before → `data_fresh: false` and `/healthz` still 200; a newer `rejected` run doesn't change `data_as_of`. Keep `tests/test_app_basics.py` passing.
  - Verify: `python -m permitmap.load_fixture && dbt build --project-dir dbt --profiles-dir dbt -s +fct_open_permits && python -m pytest tests/test_api_freshness.py tests/test_app_basics.py -q`

## 6. Freshness label and README

- [ ] 6.1 Add `#freshness` (bottom-left, A7) to `permitmap/app/static/index.html`, `style.css` and `app.js`, filled from `/api/config` per the `permit-map` delta (date formatted in America/Los_Angeles with `Intl.DateTimeFormat`, amber `#D97706` when stale). Add a "Daily refresh" section to `README.md`: `python -m permitmap.ingest` for a one-off run, `dagster dev -m permitmap.orchestration.definitions` to run the schedule, and how to read `ingest_runs` and the quarantine table. Write `tests/ui/test_freshness.py` using `page.route("**/api/config")` for the three cases: "Permits as of Nov 3" for `2026-11-03T13:05:00Z` fresh; amber and ", may be out of date" when stale; "Sample data" when null.
  - Verify: `export PW_CHROMIUM_PATH=${PW_CHROMIUM_PATH:-/opt/pw-browsers/chromium} && python -m permitmap.load_fixture && dbt build --project-dir dbt --profiles-dir dbt -s +fct_open_permits && python -m pytest tests/ui/test_freshness.py -q && python -m pytest -q`
