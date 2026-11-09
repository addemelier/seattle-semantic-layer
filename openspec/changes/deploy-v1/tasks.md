# Tasks: deploy-v1

Every task runs offline (PyPI only). Nothing builds or runs containers. Read design.md "Decisions" and "Build notes" first.

## 1. App picks up the lake

- [ ] 1.1 Add `get_con(app)` to `permitmap/app/main.py` and use it in `freshness()`, `/healthz` and `/api/permits` (Build notes, A8). Write `tests/test_app_lake.py`: an app created with a `Config` whose catalog doesn't exist returns 503 from `/healthz` and `/api/permits` and 200 from `/api/config` with null freshness; after `load_fixture` + `dbt build` into that same path, the next `/healthz` is 200 and `/api/permits` returns fixture permits, with no new app created; the cross-process visibility test exactly as in Build notes (apply the stated fallback if it fails, and say so in the PR). Keep `tests/test_app_basics.py` and `tests/test_api_freshness.py` passing.
  - Verify: `python -m permitmap.load_fixture && dbt build --project-dir dbt --profiles-dir dbt -s +fct_open_permits && python -m pytest tests/test_app_lake.py tests/test_app_basics.py tests/test_api_freshness.py -q`

## 2. Image and wheel check

- [ ] 2.1 Create `Dockerfile` and `.dockerignore` exactly per Build notes, and `permitmap/deploy/__init__.py` and `permitmap/deploy/check_wheels.py`. Write the Dockerfile part of `tests/test_deploy_files.py` (base image, non-root `USER`, `dbt parse`, the four `ENV` paths, `EXPOSE 8000`) and `tests/test_check_wheels.py` (with `subprocess.run` monkeypatched: both platforms called with `--only-binary=:all:` and the pyproject dependencies; a failing platform makes it exit non-zero and name the platform).
  - Verify: `pip install -e '.[dev]' && python -m pytest tests/test_deploy_files.py tests/test_check_wheels.py -q && python -m permitmap.deploy.check_wheels`

## 3. Dagster instance and first-pull bootstrap

- [ ] 3.1 Create `deploy/dagster.yaml`, `deploy/workspace.yaml`, `deploy/entrypoint-daemon.sh`, `deploy/entrypoint-webserver.sh` and `permitmap/deploy/bootstrap.py` per Build notes. Add their structure checks to `tests/test_deploy_files.py`. Write `tests/test_bootstrap.py` on a temp lake (env pointing `PERMITMAP_LAKE_CATALOG`/`PERMITMAP_LAKE_DATA` at it, `subprocess.run` monkeypatched): no catalog → ingest is launched; catalog from `load_fixture` with no `ingest_runs` → launched; `ingest_runs` with only a `rejected` row → launched; with an `accepted` row → not launched and prints the skip line; the launched ingest exiting 1, or `subprocess.run` raising, still makes `main()` return 0. Also check `dagster.yaml` loads: `DAGSTER_HOME=<tmp>` with the file copied in, `python -c "from dagster import DagsterInstance; DagsterInstance.get()"` exits 0 (with `base_dir`s overridden to tmp paths in a copy for the test).
  - Verify: `python -m pytest tests/test_bootstrap.py tests/test_deploy_files.py -q && dagster definitions validate -w deploy/workspace.yaml`

## 4. Compose file and README

- [ ] 4.1 Create `docker-compose.yml` exactly per Build notes and add its structure checks to `tests/test_deploy_files.py` (all Compose assertions listed in Build notes, including the scan that no literal `EVENT_IP_SALT` value is committed). Add the "Deploy" section to `README.md` per Build notes. If the `docker` CLI is present, also run `EVENT_IP_SALT=x docker compose config -q` in the test (skip the test when `docker` is absent); don't build or pull.
  - Verify: `python -m pytest tests/test_deploy_files.py -q && python -m pytest -q`
