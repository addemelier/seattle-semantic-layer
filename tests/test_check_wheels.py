"""permitmap.deploy.check_wheels with pip mocked out (deploy-v1 task 2.1)."""

import subprocess

from permitmap.deploy import check_wheels


class _Result:
    def __init__(self, returncode, stderr=""):
        self.returncode, self.stderr, self.stdout = returncode, stderr, ""


def _fake_run(calls, fail_tag=None):
    def run(cmd, **kwargs):
        calls.append(cmd)
        if fail_tag and fail_tag in cmd:
            return _Result(1, "ERROR: No matching distribution found for somepkg")
        return _Result(0)
    return run


def test_both_platforms_checked_with_binary_only(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(subprocess, "run", _fake_run(calls))
    assert check_wheels.main() == 0
    assert len(calls) == 2
    deps = check_wheels.dependencies()
    assert deps and "fastapi" in deps
    platforms = []
    for cmd in calls:
        assert "--only-binary=:all:" in cmd
        assert "--dry-run" in cmd
        assert cmd[-len(deps):] == deps
        platforms += [cmd[i + 1] for i, a in enumerate(cmd) if a == "--platform"]
    assert {"manylinux_2_28_aarch64", "manylinux_2_28_x86_64",
            "manylinux2014_aarch64", "manylinux2014_x86_64"} <= set(platforms)
    assert "all" in capsys.readouterr().out


def test_failing_platform_exits_nonzero_and_is_named(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(subprocess, "run", _fake_run(calls, fail_tag="manylinux_2_28_aarch64"))
    assert check_wheels.main() != 0
    out = capsys.readouterr().out
    assert "linux/arm64 FAILED" in out
    assert "linux/amd64 FAILED" not in out
    assert "No matching distribution" in out
