"""Structure checks for the deployment files (deployment spec, deploy-v1).

Nothing here builds or runs a container; these tests read the files.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOCKERFILE = REPO / "Dockerfile"


# --- Dockerfile ------------------------------------------------------------

def _dockerfile_lines() -> list[str]:
    return [ln.strip() for ln in DOCKERFILE.read_text().splitlines()
            if ln.strip() and not ln.strip().startswith("#")]


def test_dockerfile_base_image():
    froms = [ln for ln in _dockerfile_lines() if ln.upper().startswith("FROM ")]
    assert froms == ["FROM python:3.11-slim-bookworm"]


def test_dockerfile_runs_as_non_root():
    users = [ln.split(None, 1)[1] for ln in _dockerfile_lines() if ln.upper().startswith("USER ")]
    assert users, "Dockerfile must switch to a non-root USER"
    assert users[-1] not in ("root", "0", "0:0")


def test_dockerfile_runs_dbt_parse():
    text = DOCKERFILE.read_text()
    assert re.search(r"^RUN .*dbt parse --project-dir dbt --profiles-dir dbt", text, re.M)


def test_dockerfile_env_paths_and_port():
    text = DOCKERFILE.read_text()
    for pair in ("PERMITMAP_LAKE_CATALOG=/data/lake/catalog.sqlite",
                 "PERMITMAP_LAKE_DATA=/data/lake/files",
                 "DAGSTER_HOME=/data/dagster",
                 "PERMITMAP_HOST=0.0.0.0",
                 "PERMITMAP_PORT=8000"):
        assert pair in text, pair
    assert "EXPOSE 8000" in _dockerfile_lines()


def test_dockerignore_keeps_data_and_secrets_out():
    entries = set((REPO / ".dockerignore").read_text().split())
    assert {".git", "data/", "tests/", ".env", "dbt/target/"} <= entries


# --- Dagster instance and entrypoints ---------------------------------------

DEPLOY = REPO / "deploy"


def _yaml(path: Path):
    import yaml
    return yaml.safe_load(path.read_text())


def test_workspace_loads_definitions_module():
    ws = _yaml(DEPLOY / "workspace.yaml")
    assert ws["load_from"] == [{"python_module": "permitmap.orchestration.definitions"}]


def test_dagster_yaml_sqlite_under_data_dagster_and_no_telemetry():
    cfg = _yaml(DEPLOY / "dagster.yaml")
    assert cfg["storage"]["sqlite"]["base_dir"].startswith("/data/dagster/")
    assert cfg["local_artifact_storage"]["config"]["base_dir"].startswith("/data/dagster/")
    assert cfg["telemetry"]["enabled"] is False
    assert cfg["run_coordinator"]["class"] == "QueuedRunCoordinator"
    assert cfg["run_coordinator"]["config"]["max_concurrent_runs"] == 1


def _script_lines(name: str) -> list[str]:
    return [ln.strip() for ln in (DEPLOY / name).read_text().splitlines()
            if ln.strip() and not ln.strip().startswith("#")]


def test_daemon_entrypoint_bootstraps_then_execs_daemon():
    lines = _script_lines("entrypoint-daemon.sh")
    assert lines[0] == "set -eu"
    assert any(ln.startswith("cp ") and 'dagster.yaml "$DAGSTER_HOME/dagster.yaml"' in ln
               for ln in lines)
    boot = next(i for i, ln in enumerate(lines) if "permitmap.deploy.bootstrap" in ln)
    assert lines[-1].startswith("exec dagster-daemon run")
    assert boot < len(lines) - 1


def test_webserver_entrypoint_execs_webserver():
    lines = _script_lines("entrypoint-webserver.sh")
    assert lines[0] == "set -eu"
    assert any(ln.startswith("cp ") and "dagster.yaml" in ln for ln in lines)
    assert lines[-1].startswith("exec dagster-webserver")
    assert "-p 3000" in lines[-1]
