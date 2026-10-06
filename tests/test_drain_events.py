import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import fakeredis
import pyarrow.parquet as pq
import pytest

from permitmap import drain_events
from permitmap.drain_events import GROUP, drain
from permitmap.events import STREAM, record_event

REPO = Path(__file__).resolve().parent.parent
T0 = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def r():
    return fakeredis.FakeRedis()


def _files(d: Path):
    return sorted(p for p in d.rglob("*.parquet"))


def _rows(d: Path):
    return sum(pq.read_table(p).num_rows for p in _files(d))


def _record(r, n, start=T0):
    for i in range(n):
        record_event(r, "map_move", f"s{i}", lat=47.6681, lon=-122.3845,
                     now=start + timedelta(minutes=i))


def test_ten_events_then_second_drain_writes_nothing(r, tmp_path):
    _record(r, 10)
    assert drain(r, tmp_path) == 10
    assert _rows(tmp_path) == 10
    files_after_first = _files(tmp_path)

    assert drain(r, tmp_path) == 0
    assert _files(tmp_path) == files_after_first
    assert _rows(tmp_path) == 10


def test_partition_path_and_types(r, tmp_path):
    _record(r, 3)
    drain(r, tmp_path)
    [f] = _files(tmp_path)
    first_id = r.xrange(STREAM, count=1)[0][0].decode()
    assert f == tmp_path / "date=2026-10-05" / f"part-{first_id}.parquet"
    t = pq.read_table(f)
    assert t.column("lat").to_pylist() == [47.668] * 3
    assert str(t.schema.field("ts").type) == "timestamp[us, tz=UTC]"


def test_two_dates_two_partitions(r, tmp_path):
    _record(r, 2, start=datetime(2026, 10, 5, 23, 58, tzinfo=timezone.utc))
    _record(r, 2, start=datetime(2026, 10, 6, 0, 5, tzinfo=timezone.utc))
    assert drain(r, tmp_path) == 4
    parts = sorted(p.name for p in tmp_path.iterdir())
    assert parts == ["date=2026-10-05", "date=2026-10-06"]
    assert _rows(tmp_path) == 4


def test_small_batches(r, tmp_path):
    _record(r, 10)
    assert drain(r, tmp_path, batch_size=3) == 10
    assert _rows(tmp_path) == 10


def test_write_failure_leaves_events_pending_then_recovers(r, tmp_path, monkeypatch):
    _record(r, 10)

    def boom(table, path):
        raise OSError("disk full")

    monkeypatch.setattr(drain_events, "_write_parquet", boom)
    with pytest.raises(OSError):
        drain(r, tmp_path, consumer="c1")
    assert r.xpending(STREAM, GROUP)["pending"] == 10
    assert _files(tmp_path) == []

    monkeypatch.undo()
    assert drain(r, tmp_path, consumer="c1") == 10
    assert r.xpending(STREAM, GROUP)["pending"] == 0
    assert _rows(tmp_path) == 10


def test_landing_path_is_gitignored():
    path = "data/landing/events/date=2026-10-05/part-1-0.parquet"
    res = subprocess.run(["git", "check-ignore", "-q", path], cwd=REPO)
    assert res.returncode == 0
