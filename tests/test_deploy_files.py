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


# --- docker-compose.yml -----------------------------------------------------

import os
import shutil
import subprocess

import pytest

COMPOSE = REPO / "docker-compose.yml"
PYTHON_SERVICES = ("app", "dagster-daemon", "dagster-webserver")


def _compose():
    return _yaml(COMPOSE)


def test_compose_has_exactly_four_services_and_no_version_key():
    cfg = _compose()
    assert "version" not in cfg
    assert set(cfg["services"]) == {"app", "dagster-daemon", "dagster-webserver", "redis"}


def test_compose_only_webserver_publishes_ports_on_localhost():
    services = _compose()["services"]
    with_ports = {name for name, svc in services.items() if svc.get("ports")}
    assert with_ports == {"dagster-webserver"}
    for mapping in services["dagster-webserver"]["ports"]:
        assert str(mapping).startswith("127.0.0.1:"), mapping


def test_compose_app_exposes_8000_and_healthchecks_api_config():
    app = _compose()["services"]["app"]
    assert [str(p) for p in app["expose"]] == ["8000"]
    assert "ports" not in app
    test = app["healthcheck"]["test"]
    assert "/api/config" in " ".join(test)
    assert "/healthz" not in " ".join(test)


def test_compose_app_requires_event_ip_salt_and_trusts_proxy():
    env = _compose()["services"]["app"]["environment"]
    assert re.fullmatch(r"\$\{EVENT_IP_SALT:\?[^}]+\}", env["EVENT_IP_SALT"])
    assert str(env["PERMITMAP_TRUST_PROXY"]) == "1"


def test_compose_python_services_share_env_and_mount_lake():
    services = _compose()["services"]
    for name in PYTHON_SERVICES:
        svc = services[name]
        assert svc["build"] == "."
        assert svc["restart"] == "unless-stopped"
        assert "lake:/data/lake" in svc["volumes"], name
        env = svc["environment"]
        assert env["PERMITMAP_LAKE_CATALOG"] == "/data/lake/catalog.sqlite"
        assert env["PERMITMAP_LAKE_DATA"] == "/data/lake/files"
        assert env["DAGSTER_HOME"] == "/data/dagster"
        assert env["REDIS_URL"] == "redis://redis:6379/0"
        assert env["PERMITMAP_SOCRATA_URL"].startswith("${PERMITMAP_SOCRATA_URL:-https://")


def test_compose_dagster_services_mount_dagster_home_and_run_entrypoints():
    services = _compose()["services"]
    for name, script in (("dagster-daemon", "entrypoint-daemon.sh"),
                         ("dagster-webserver", "entrypoint-webserver.sh")):
        svc = services[name]
        assert "dagster_home:/data/dagster" in svc["volumes"], name
        assert svc["command"] == ["sh", f"/app/deploy/{script}"]


def test_compose_redis_appendonly_with_volume_and_no_ports():
    redis = _compose()["services"]["redis"]
    assert redis["image"] == "redis:8-alpine"
    assert "ports" not in redis
    cmd = redis["command"]
    assert "--appendonly" in cmd and cmd[cmd.index("--appendonly") + 1] == "yes"
    assert "redis_data:/data" in redis["volumes"]


def test_compose_declares_three_volumes():
    assert set(_compose()["volumes"]) == {"lake", "redis_data", "dagster_home"}


# Placeholder values that are not secrets: "x" is the dummy the deploy-v1
# tasks use for `docker compose config`.
_SALT_PLACEHOLDERS = {"x"}


def test_no_literal_event_ip_salt_committed():
    files = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=REPO,
                           capture_output=True, text=True, check=True).stdout.split()
    pattern = re.compile(r"(?<!\{)EVENT_IP_SALT\s*[:=]\s*[\"']?([^\s\"'`]+)")
    offenders = []
    for rel in files:
        if rel.startswith("tests/"):
            continue
        path = REPO / rel
        try:
            text = path.read_text()
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        for m in pattern.finditer(text):
            value = m.group(1)
            if value.startswith("${") or value in _SALT_PLACEHOLDERS:
                continue
            offenders.append(f"{rel}: {m.group(0)}")
    assert not offenders, offenders


def _docker_compose_env(**extra):
    env = {k: v for k, v in os.environ.items() if k != "EVENT_IP_SALT"}
    env.update(extra)
    return env


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker CLI not installed")
def test_docker_compose_config_validates():
    ok = subprocess.run(["docker", "compose", "config", "-q"], cwd=REPO,
                        env=_docker_compose_env(EVENT_IP_SALT="x"),
                        capture_output=True, text=True)
    assert ok.returncode == 0, ok.stderr
    missing = subprocess.run(["docker", "compose", "config", "-q"], cwd=REPO,
                             env=_docker_compose_env(), capture_output=True, text=True)
    assert missing.returncode != 0
    assert "EVENT_IP_SALT" in missing.stderr
