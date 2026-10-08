from permitmap.lake import connect_lake


def test_table_survives_reconnect(tmp_path):
    catalog = tmp_path / "lake" / "catalog.sqlite"
    files = tmp_path / "lake" / "files"

    con = connect_lake(catalog, files)
    con.execute("CREATE TABLE lake.t AS SELECT 1 AS id, 'ballard' AS hood")
    con.close()

    assert catalog.exists()

    con = connect_lake(catalog, files)
    rows = con.execute("SELECT id, hood FROM lake.t").fetchall()
    con.close()
    assert rows == [(1, "ballard")]
