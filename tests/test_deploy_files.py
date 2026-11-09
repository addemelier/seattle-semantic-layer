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
