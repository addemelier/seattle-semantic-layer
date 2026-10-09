"""FastAPI app factory for the permit map."""

from __future__ import annotations

from pathlib import Path

import duckdb
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from permitmap.app.config import Config
from permitmap.lake import connect_lake

STATIC = Path(__file__).resolve().parent / "static"


def _open_lake(config: Config) -> duckdb.DuckDBPyConnection | None:
    # connect_lake would create an empty catalog, so only open one that already exists.
    if not Path(config.lake_catalog).is_file():
        return None
    try:
        return connect_lake(config.lake_catalog, config.lake_data)
    except duckdb.Error:
        return None


def create_app(config: Config | None = None) -> FastAPI:
    config = config or Config.from_env()
    app = FastAPI(title="Seattle permit map")
    app.state.config = config
    app.state.con = _open_lake(config)

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html", media_type="text/html")

    @app.get("/healthz")
    def healthz() -> JSONResponse:
        con = app.state.con
        if con is None:
            return JSONResponse({"status": "unavailable"}, status_code=503)
        try:
            con.cursor().execute("SELECT 1 FROM lake.gold.fct_open_permits LIMIT 1").fetchall()
        except duckdb.Error:
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return JSONResponse({"status": "ok"})

    @app.get("/api/config")
    def api_config() -> dict:
        return {"style_url": config.style_url}

    return app
