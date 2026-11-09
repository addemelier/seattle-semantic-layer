"""End-to-end ingest on a temp lake with the Socrata endpoint mocked by respx."""

from pathlib import Path

import httpx
import pytest
import respx

from permitmap.app.config import Config
from permitmap.ingest.__main__ import main
from permitmap.ingest.load import INGEST_RUNS
from permitmap.ingest.pipeline import IngestRejected, run_ingest
from permitmap.lake import connect_lake

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "tests" / "fixtures" / "sdci_building_permits_sample.csv"
URL = "https://socrata.test/resource/76t5-zqzr.csv"
PAGE_SIZE = 15


def _pages() -> dict[str, str]:
    header, *rows = FIXTURE.read_text().splitlines(keepends=True)
    return {str(i): header + "".join(rows[i:i + PAGE_SIZE]) for i in range(0, len(rows) + 1, PAGE_SIZE)}


def _serve_fixture():
    pages = _pages()
    return respx.get(URL).mock(
        side_effect=lambda req: httpx.Response(200, text=pages[req.url.params["$offset"]]))


def _query(config: Config, sql: str):
    con = connect_lake(config.lake_catalog, config.lake_data)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _repo_gold_count() -> int:
    repo = Config(lake_catalog=str(REPO / "data/lake/catalog.sqlite"),
                  lake_data=str(REPO / "data/lake/files"))
    if not Path(repo.lake_catalog).exists():
        pytest.fail("lake not built: run load_fixture and dbt build first")
    return _query(repo, "SELECT count(*) FROM lake.gold.fct_open_permits")[0][0]


@pytest.fixture(scope="module")
def config(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("lake")
    return Config(lake_catalog=str(tmp / "catalog.sqlite"), lake_data=str(tmp / "files"),
                  socrata_url=URL)


@pytest.fixture(scope="module")
def accepted_run(config):
    with respx.mock:
        route = _serve_fixture()
        with httpx.Client() as c:
            code = main([], config=config, client=c, page_size=PAGE_SIZE, sleep=lambda s: None)
        assert route.call_count == 3  # 15 + 15 + 11 rows
    return code


def test_accepted_run_builds_gold(config, accepted_run):
    assert accepted_run == 0
    runs = _query(config, f"SELECT status, reason, rows_fetched, rows_valid FROM {INGEST_RUNS}")
    assert runs == [("accepted", None, 41, 41)]
    gold = _query(config, "SELECT count(*) FROM lake.gold.fct_open_permits")[0][0]
    assert gold == _repo_gold_count() > 0


def test_fetch_failure_rejected_and_gold_unchanged(config, accepted_run):
    gold_before = _query(config, "SELECT count(*) FROM lake.gold.fct_open_permits")[0][0]
    with respx.mock:
        respx.get(URL).mock(return_value=httpx.Response(500))
        with httpx.Client() as c:
            with pytest.raises(IngestRejected) as e:
                run_ingest(config, c, page_size=PAGE_SIZE, sleep=lambda s: None)
            assert e.value.result.reason.startswith("fetch failed:")
            assert main([], config=config, client=c, page_size=PAGE_SIZE, sleep=lambda s: None) == 1
    runs = _query(config, f"SELECT status, reason FROM {INGEST_RUNS} ORDER BY finished_at")
    assert [r[0] for r in runs] == ["accepted", "rejected", "rejected"]
    assert all(r[1].startswith("fetch failed:") for r in runs[1:])
    assert _query(config, "SELECT count(*) FROM lake.gold.fct_open_permits")[0][0] == gold_before
    assert _query(config, "SELECT count(*) FROM lake.bronze.sdci_building_permits")[0][0] == 41
