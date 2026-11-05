"""POST /api/events: validate a page event and record it on the events:v1 stream."""

from __future__ import annotations

import json
import re
from typing import Any

import redis
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from permitmap.events import record_event

MAX_BODY_BYTES = 2048
MAX_USER_AGENT = 300
ALLOWED_KEYS = ("event_type", "session_id", "search_text", "lat", "lon", "filters",
                "permit_id", "referrer")
SESSION_ID = re.compile(r"^[0-9a-f]{32}$")
MAX_LEN = {"search_text": 200, "permit_id": 64, "referrer": 500}
FILTER_KEYS = ("stage", "work_type")


class BadEvent(ValueError):
    pass


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate(body: Any) -> dict:
    """Return the event fields, or raise BadEvent with a message naming the problem."""
    if not isinstance(body, dict):
        raise BadEvent("body must be a JSON object")
    for key in body:
        if key not in ALLOWED_KEYS:
            raise BadEvent(f"unexpected field {key!r}")
    if not isinstance(body.get("event_type"), str):
        raise BadEvent("event_type is required")
    sid = body.get("session_id")
    if not isinstance(sid, str) or not SESSION_ID.match(sid):
        raise BadEvent("session_id must be 32 lowercase hex characters")
    for key, limit in MAX_LEN.items():
        v = body.get(key)
        if v is None:
            continue
        if not isinstance(v, str):
            raise BadEvent(f"{key} must be a string")
        if len(v) > limit:
            raise BadEvent(f"{key} must be at most {limit} characters")
    for key in ("lat", "lon"):
        if body.get(key) is not None and not _is_number(body[key]):
            raise BadEvent(f"{key} must be a number")
    filters = body.get("filters")
    if filters is not None:
        if not isinstance(filters, dict):
            raise BadEvent("filters must be an object")
        for k, v in filters.items():
            if k not in FILTER_KEYS:
                raise BadEvent(f"filters may only have {', '.join(FILTER_KEYS)}; got {k!r}")
            if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
                raise BadEvent(f"filters.{k} must be a list of strings")
    return body


def client_ip(request: Request, trust_proxy: bool) -> str | None:
    if trust_proxy:
        fwd = request.headers.get("x-forwarded-for", "")
        first = fwd.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else None


def register(app: FastAPI) -> None:
    @app.post("/api/events")
    async def api_events(request: Request) -> Response:
        raw = await request.body()
        if len(raw) > MAX_BODY_BYTES:
            return JSONResponse({"error": f"body over {MAX_BODY_BYTES} bytes"}, status_code=413)
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            return JSONResponse({"error": "body must be JSON"}, status_code=400)
        try:
            event = validate(body)
        except BadEvent as e:
            return JSONResponse({"error": str(e)}, status_code=400)

        r = app.state.redis
        if r is None:
            return JSONResponse({"error": "events disabled"}, status_code=503)
        ua = request.headers.get("user-agent")
        try:
            record_event(
                r, event["event_type"], event["session_id"],
                search_text=event.get("search_text"), lat=event.get("lat"), lon=event.get("lon"),
                filters=event.get("filters"), permit_id=event.get("permit_id"),
                referrer=event.get("referrer"),
                user_agent=ua[:MAX_USER_AGENT] if ua else None,
                ip=client_ip(request, app.state.config.trust_proxy),
            )
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        except redis.exceptions.RedisError:
            return JSONResponse({"error": "events unavailable"}, status_code=503)
        return Response(status_code=204)
