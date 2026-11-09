# BLOCKED: deploy-v1 (build run 2026-11-09)

Tasks 1.1, 2.1 and 3.1 are done and verified on `build/deploy-v1`. Task 4.1 is not started.

## The task

Found while doing **3.1** (Dagster instance + `deploy/workspace.yaml`); the cause is the **2.1** Dockerfile as written in design.md "Build notes". Task 4.1 itself is not affected, but shipping 4.1 makes the stack deployable, and with this bug the Dagster daemon and webserver would not start on the Pi (D4 auto-deploys on merge).

## What's wrong

The Build notes say `pip install .` (a regular, non-editable install). That copies `permitmap/` into `site-packages`. Both `permitmap/orchestration/definitions.py` and `permitmap/ingest/__main__.py` find the dbt project with `Path(__file__).resolve().parents[2] / "dbt"`. From `site-packages` that points to `/usr/local/lib/python3.11/dbt`, which doesn't exist.

- The app (`python -m permitmap.app`) and the bootstrap's ingest (`cwd=/app`) are fine: `python -m` puts the working directory first on `sys.path`, so `/app/permitmap` wins.
- **Dagster is not fine.** Loading `deploy/workspace.yaml` imports the `site-packages` copy, so the definitions fail with `DagsterDbtProjectNotFoundError`. The daemon, the webserver and the 5:00am schedule would all be down.

## What I tried

I copied the image layout (`pyproject.toml`, `permitmap/`, `dbt/`, `deploy/`, then `pip install .` into a venv and `dbt parse`) into a scratch `app/` directory and ran `dagster definitions validate -w deploy/workspace.yaml` from inside it:

- As specified: **fails**, with `project_dir .../site-packages/dbt does not exist`.
- With `PYTHONPATH=<app dir>`: passes.
- With `working_directory: <app dir>` added to the `python_module` entry in `workspace.yaml`: passes.

The in-repo verification (`dagster definitions validate` from the repo root) passes only because the dev install is editable, so it doesn't catch this.

## Decision needed

May the builder change the Dockerfile from the Build notes so that Dagster loads `/app/permitmap` instead of the `site-packages` copy? If yes, which fix?

1. Add `PYTHONPATH=/app` to the Dockerfile's runtime `ENV` line, plus a test assertion for it in `tests/test_deploy_files.py`.
2. Add `working_directory: /app` to `deploy/workspace.yaml`.
3. Use `pip install -e .` instead of `pip install .`.

## Recommended answer

**Option 1 (`ENV PYTHONPATH=/app`).** It's one line, and it covers every process in the image (daemon, webserver, Dagster run workers, the app) whatever their working directory. Option 2 only fixes workspace loading, and option 3 adds setuptools' editable-install machinery to a production image.

If you approve, update the Dockerfile bullet in design.md, delete this file, and the next build run does the fix and then task 4.1.
