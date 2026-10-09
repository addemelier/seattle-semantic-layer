"""FastAPI app factory for the permit map."""

from __future__ import annotations

from pathlib import Path

import duckdb
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from permitmap.app import geocode, permits
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

    @app.get("/api/permits")
    def api_permits(request: Request) -> JSONResponse:
        q = request.query_params
        try:
            bbox = permits.parse_bbox(q.get("bbox"))
            stages = permits.parse_list("stage", q.get("stage"), permits.STAGES)
            work_types = permits.parse_list("work_type", q.get("work_type"), permits.WORK_TYPES)
        except permits.BadRequest as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        if app.state.con is None:
            return JSONResponse({"error": "permit data is unavailable"}, status_code=503)
        return JSONResponse(permits.query_permits(app.state.con, bbox, stages, work_types))

    @app.get("/api/geocode")
    async def api_geocode(q: str | None = None) -> JSONResponse:
        q = (q or "").strip()
        if not 3 <= len(q) <= 200:
            return JSONResponse({"error": "q must be 3-200 characters"}, status_code=400)
        try:
            async with httpx.AsyncClient() as client:
                match = await geocode.geocode(client, config.geocoder_url, q)
        except geocode.GeocoderUnavailable:
            return JSONResponse({"error": "address search is unavailable right now"},
                                status_code=502)
        if match is None:
            return JSONResponse({"error": "address not found in Seattle"}, status_code=404)
        return JSONResponse({"lat": match.lat, "lon": match.lon,
                             "matched_address": match.matched_address, "score": match.score})

    return app
