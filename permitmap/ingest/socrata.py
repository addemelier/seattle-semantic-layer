"""Page through a Socrata CSV endpoint and write each page to disk."""

from __future__ import annotations

import csv
import io
import time
from collections.abc import Callable
from pathlib import Path

import httpx

TIMEOUT_SECONDS = 60.0
ATTEMPTS = 3
BACKOFF_SECONDS = (2, 4, 8)


class FetchFailed(Exception):
    """A page could not be fetched after every retry."""


def _data_rows(text: str) -> int:
    rows = list(csv.reader(io.StringIO(text)))
    return max(len(rows) - 1, 0)  # minus header


def _get_page(client: httpx.Client, url: str, params: dict, sleep: Callable[[float], None]) -> str:
    last: Exception | None = None
    for attempt in range(ATTEMPTS):
        try:
            r = client.get(url, params=params, timeout=TIMEOUT_SECONDS)
            r.raise_for_status()
            return r.text
        except httpx.HTTPError as e:
            last = e
            if attempt < ATTEMPTS - 1:
                sleep(BACKOFF_SECONDS[attempt])
    raise FetchFailed(f"offset {params['$offset']}: {last}") from last


def fetch_pages(client: httpx.Client, url: str, out_dir: Path, page_size: int = 50000,
                sleep: Callable[[float], None] = time.sleep) -> list[Path]:
    """Fetch every page (`$order=:id`, `$limit`, `$offset`) until a short page.

    Each page is written to `out_dir/page-NNNN.csv`. Each page gets 3 attempts with
    waits from BACKOFF_SECONDS between them; FetchFailed is raised after the third
    failure (no wait after the last attempt). `sleep` is injectable for tests.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    offset = 0
    while True:
        params = {"$order": ":id", "$limit": page_size, "$offset": offset}
        text = _get_page(client, url, params, sleep)
        path = out_dir / f"page-{len(paths):04d}.csv"
        path.write_text(text, encoding="utf-8")
        paths.append(path)
        if _data_rows(text) < page_size:
            return paths
        offset += page_size
