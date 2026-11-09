"""Socrata paging and retries (all HTTP mocked)."""

from pathlib import Path

import httpx
import pytest
import respx

from permitmap.app.config import DEFAULT_SOCRATA_URL, Config
from permitmap.ingest.socrata import FetchFailed, fetch_pages

URL = "https://socrata.test/resource/x.csv"
HEADER = "permitnum,latitude\n"


def _page(n: int, start: int = 0) -> str:
    return HEADER + "".join(f"P{start + i},47.6\n" for i in range(n))


@respx.mock
def test_three_pages_then_stop(tmp_path):
    pages = {"0": _page(3, 0), "3": _page(3, 3), "6": _page(1, 6)}
    route = respx.get(URL).mock(
        side_effect=lambda req: httpx.Response(200, text=pages[req.url.params["$offset"]]))
    with httpx.Client() as c:
        paths = fetch_pages(c, URL, tmp_path, page_size=3, sleep=lambda s: None)
    assert [p.name for p in paths] == ["page-0000.csv", "page-0001.csv", "page-0002.csv"]
    assert all(Path(p).is_file() for p in paths)
    assert route.call_count == 3
    for call, offset in zip(route.calls, ["0", "3", "6"]):
        params = call.request.url.params
        assert params["$order"] == ":id"
        assert params["$limit"] == "3"
        assert params["$offset"] == offset


@respx.mock
def test_retry_then_success(tmp_path):
    respx.get(URL).mock(side_effect=[httpx.Response(500), httpx.Response(503),
                                     httpx.Response(200, text=_page(1))])
    sleeps: list[float] = []
    with httpx.Client() as c:
        paths = fetch_pages(c, URL, tmp_path, page_size=3, sleep=sleeps.append)
    assert len(paths) == 1
    assert sleeps == [2, 4]


@respx.mock
def test_three_failures_raise(tmp_path):
    route = respx.get(URL).mock(return_value=httpx.Response(500))
    with httpx.Client() as c, pytest.raises(FetchFailed):
        fetch_pages(c, URL, tmp_path, page_size=3, sleep=lambda s: None)
    assert route.call_count == 3


@respx.mock
def test_timeout_is_retried(tmp_path):
    respx.get(URL).mock(side_effect=[httpx.ReadTimeout("slow"), httpx.Response(200, text=_page(0))])
    with httpx.Client() as c:
        assert len(fetch_pages(c, URL, tmp_path, page_size=3, sleep=lambda s: None)) == 1


def test_socrata_url_config():
    assert Config().socrata_url == DEFAULT_SOCRATA_URL
    assert Config.from_env({}).socrata_url == "https://cos-data.seattle.gov/resource/76t5-zqzr.csv"
    assert Config.from_env({"PERMITMAP_SOCRATA_URL": URL}).socrata_url == URL
