"""Seattle address geocoding through the City of Seattle ArcGIS locator (permit-api spec)."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

MIN_SCORE = 80
TIMEOUT_SECONDS = 5.0


class GeocoderUnavailable(Exception):
    """The locator timed out, errored, or returned something we can't read."""


@dataclass(frozen=True)
class Match:
    lat: float
    lon: float
    matched_address: str
    score: float


async def geocode(client: httpx.AsyncClient, url: str, q: str) -> Match | None:
    """Best candidate scoring >= MIN_SCORE, or None. Raises GeocoderUnavailable."""
    params = {"SingleLine": q, "outSR": "4326", "maxLocations": "5", "f": "json"}
    try:
        resp = await client.get(url, params=params, timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
        body = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        raise GeocoderUnavailable(str(e) or type(e).__name__) from e

    if not isinstance(body, dict):
        raise GeocoderUnavailable("locator returned a non-object body")
    if "error" in body:
        raise GeocoderUnavailable(f"locator error: {body['error']}")
    candidates = body.get("candidates")
    if not isinstance(candidates, list):
        raise GeocoderUnavailable("locator response has no candidates list")
    if not candidates:
        return None

    try:
        parsed = [
            Match(lat=float(c["location"]["y"]), lon=float(c["location"]["x"]),
                  matched_address=str(c["address"]), score=float(c["score"]))
            for c in candidates
        ]
    except (KeyError, TypeError, ValueError) as e:
        raise GeocoderUnavailable("locator returned a malformed candidate") from e

    best = max(parsed, key=lambda m: m.score)
    return best if best.score >= MIN_SCORE else None
