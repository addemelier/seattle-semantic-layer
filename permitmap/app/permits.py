"""Open permits in a bounding box, as GeoJSON (permit-api spec)."""

from __future__ import annotations

import datetime as dt
import math
from decimal import Decimal

import duckdb

MAX_FEATURES = 2000

STAGES = ("in_review", "issued")
WORK_TYPES = ("new_building", "addition_alteration", "demolition", "adu")

PROPERTY_COLUMNS = (
    "permit_id", "address", "description", "work_type", "stage", "status_raw",
    "applied_date", "issued_date", "expires_date", "valuation_usd",
    "housing_units_added", "housing_units_removed", "contractor", "permit_url",
)


class BadRequest(ValueError):
    """A request parameter is invalid; the message is safe to show the caller."""


def parse_bbox(raw: str | None) -> tuple[float, float, float, float]:
    if raw is None or not raw.strip():
        raise BadRequest("bbox is required: min_lon,min_lat,max_lon,max_lat")
    parts = raw.split(",")
    if len(parts) != 4:
        raise BadRequest("bbox must have four numbers: min_lon,min_lat,max_lon,max_lat")
    try:
        min_lon, min_lat, max_lon, max_lat = (float(p) for p in parts)
    except ValueError:
        raise BadRequest("bbox must have four numbers: min_lon,min_lat,max_lon,max_lat") from None
    if not all(math.isfinite(v) for v in (min_lon, min_lat, max_lon, max_lat)):
        raise BadRequest("bbox must have four finite numbers")
    if min_lon > max_lon or min_lat > max_lat:
        raise BadRequest("bbox min must not be greater than max")
    if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180
            and -90 <= min_lat <= 90 and -90 <= max_lat <= 90):
        raise BadRequest("bbox is out of range: longitude -180..180, latitude -90..90")
    return min_lon, min_lat, max_lon, max_lat


def parse_list(name: str, raw: str | None, allowed: tuple[str, ...]) -> list[str] | None:
    """None = no filter. Empty string = filter that matches nothing."""
    if raw is None:
        return None
    values = [v.strip() for v in raw.split(",") if v.strip()]
    unknown = [v for v in values if v not in allowed]
    if unknown:
        raise BadRequest(f"unknown {name} value(s): {', '.join(unknown)}; allowed: {', '.join(allowed)}")
    return values


def _json_value(v):
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def query_permits(con: duckdb.DuckDBPyConnection, bbox: tuple[float, float, float, float],
                  stages: list[str] | None, work_types: list[str] | None) -> dict:
    min_lon, min_lat, max_lon, max_lat = bbox
    cols = ", ".join(PROPERTY_COLUMNS)
    sql = [f"SELECT {cols}, longitude, latitude FROM lake.gold.fct_open_permits "
           "WHERE longitude BETWEEN ? AND ? AND latitude BETWEEN ? AND ?"]
    params: list = [min_lon, max_lon, min_lat, max_lat]
    for col, values in (("stage", stages), ("work_type", work_types)):
        if values is None:
            continue
        if not values:
            sql.append("AND FALSE")
            continue
        sql.append(f"AND {col} IN ({', '.join('?' for _ in values)})")
        params.extend(values)
    sql.append("ORDER BY applied_date DESC NULLS LAST, permit_id LIMIT ?")
    params.append(MAX_FEATURES + 1)

    rows = con.cursor().execute(" ".join(sql), params).fetchall()
    truncated = len(rows) > MAX_FEATURES
    rows = rows[:MAX_FEATURES]
    n = len(PROPERTY_COLUMNS)
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [row[n], row[n + 1]]},
            "properties": {c: _json_value(v) for c, v in zip(PROPERTY_COLUMNS, row[:n])},
        }
        for row in rows
    ]
    return {"type": "FeatureCollection", "features": features, "truncated": truncated}
