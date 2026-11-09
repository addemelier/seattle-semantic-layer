"""Check every runtime dependency installs from wheels on linux arm64 and amd64.

Usage: python -m permitmap.deploy.check_wheels

Runs `pip install --dry-run --only-binary=:all:` for each platform against the
[project].dependencies in pyproject.toml. Exits 0 only if both platforms resolve;
otherwise names the failing platform and prints pip's message.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PYPROJECT = REPO / "pyproject.toml"

# Each platform is tried under the newer and the older manylinux tag, so either matches.
PLATFORMS = {
    "linux/arm64": ("manylinux_2_28_aarch64", "manylinux2014_aarch64"),
    "linux/amd64": ("manylinux_2_28_x86_64", "manylinux2014_x86_64"),
}


def dependencies(pyproject: Path = PYPROJECT) -> list[str]:
    with pyproject.open("rb") as f:
        return list(tomllib.load(f)["project"]["dependencies"])


def pip_command(tags: tuple[str, ...], deps: list[str], target: str) -> list[str]:
    cmd = [sys.executable, "-m", "pip", "install", "--dry-run", "--quiet", "--ignore-installed",
           "--only-binary=:all:"]
    for tag in tags:
        cmd += ["--platform", tag]
    cmd += ["--python-version", "3.11", "--implementation", "cp", "--target", target, *deps]
    return cmd


def check(deps: list[str]) -> list[tuple[str, str]]:
    """Return (platform, pip output) for every platform that failed."""
    failures = []
    for name, tags in PLATFORMS.items():
        with tempfile.TemporaryDirectory() as target:
            res = subprocess.run(pip_command(tags, deps, target), capture_output=True, text=True)
        if res.returncode != 0:
            failures.append((name, (res.stderr or res.stdout or "").strip()))
    return failures


def main() -> int:
    deps = dependencies()
    failures = check(deps)
    for name, message in failures:
        print(f"check_wheels: {name} FAILED: not every dependency has a wheel")
        print(message)
    if failures:
        return 1
    print(f"check_wheels: all {len(deps)} dependencies install from wheels on "
          + " and ".join(PLATFORMS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
