"""Drain engagement events from the Redis Stream to date-partitioned Parquet.

Usage: python -m permitmap.drain_events   (Redis URL from env REDIS_URL)

Reads events:v1 through consumer group `drainer`, writes
<landing_dir>/date=YYYY-MM-DD/part-<first-stream-id>.parquet (event UTC date),
and XACKs only after the file is written. A crash before the ack leaves the
events pending; the next run re-reads this consumer's pending entries first,
and rewrites the same file name, so nothing is lost or duplicated.
"""

from __future__ import annotations

import argparse
import os
import socket
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from redis.exceptions import ResponseError

from permitmap.events import FIELDS, STREAM

GROUP = "drainer"
REPO = Path(__file__).resolve().parent.parent
DEFAULT_LANDING = REPO / "data" / "landing" / "events"

SCHEMA = pa.schema(
    [("stream_id", pa.string())]
    + [
        (f, pa.timestamp("us", tz="UTC") if f == "ts"
         else pa.float64() if f in ("lat", "lon")
         else pa.string())
        for f in FIELDS
    ]
)


def _s(v):
    return v.decode() if isinstance(v, bytes) else v


def ensure_group(r) -> None:
    try:
        r.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise


def _row(stream_id, fields) -> dict:
    f = {_s(k): _s(v) for k, v in fields.items()}
    row = {"stream_id": _s(stream_id)}
    for name in FIELDS:
        v = f.get(name)
        if v is not None and name in ("lat", "lon"):
            v = float(v)
        elif v is not None and name == "ts":
            v = datetime.fromisoformat(v)
        row[name] = v
    return row


def _write_parquet(table: pa.Table, path: Path) -> None:
    """Write atomically: a crash never leaves a partial file at `path`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".parquet.tmp")
    pq.write_table(table, tmp)
    os.replace(tmp, path)


def _write_batch(entries, landing_dir: Path) -> int:
    by_date: dict[str, list[dict]] = defaultdict(list)
    for stream_id, fields in entries:
        row = _row(stream_id, fields)
        by_date[row["ts"].date().isoformat()].append(row)
    for day, rows in by_date.items():
        first_id = rows[0]["stream_id"]
        path = landing_dir / f"date={day}" / f"part-{first_id}.parquet"
        _write_parquet(pa.Table.from_pylist(rows, schema=SCHEMA), path)
    return len(entries)


def drain(r, landing_dir: str | Path = DEFAULT_LANDING, batch_size: int = 1000,
          consumer: str | None = None) -> int:
    """Move all pending and new events to Parquet. Returns the number of events written."""
    landing_dir = Path(landing_dir)
    consumer = consumer or f"drainer-{socket.gethostname()}"
    ensure_group(r)

    written = 0
    # "0" re-reads this consumer's unacked (pending) entries; ">" reads new ones.
    for start in ("0", ">"):
        while True:
            resp = r.xreadgroup(GROUP, consumer, {STREAM: start}, count=batch_size)
            entries = resp[0][1] if resp else []
            if not entries:
                break
            written += _write_batch(entries, landing_dir)
            r.xack(STREAM, GROUP, *[eid for eid, _ in entries])
    return written


def main() -> None:
    import redis

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--landing-dir", type=Path, default=DEFAULT_LANDING)
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args()
    r = redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    n = drain(r, args.landing_dir, args.batch_size)
    print(f"drained {n} events to {args.landing_dir}")


if __name__ == "__main__":
    main()
