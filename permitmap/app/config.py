"""App configuration, read once from environment variables at startup."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_LAKE_CATALOG = "data/lake/catalog.sqlite"
DEFAULT_LAKE_DATA = "data/lake/files"
DEFAULT_STYLE_URL = "https://tiles.openfreemap.org/styles/positron"
DEFAULT_GEOCODER_URL = (
    "https://gisdata.seattle.gov/cosgis/rest/services/locators/MultiRoles/"
    "GeocodeServer/findAddressCandidates"
)


@dataclass(frozen=True)
class Config:
    lake_catalog: str = DEFAULT_LAKE_CATALOG
    lake_data: str = DEFAULT_LAKE_DATA
    style_url: str = DEFAULT_STYLE_URL
    geocoder_url: str = DEFAULT_GEOCODER_URL
    host: str = "127.0.0.1"
    port: int = 8000

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Config":
        env = os.environ if env is None else env
        return cls(
            lake_catalog=env.get("PERMITMAP_LAKE_CATALOG", DEFAULT_LAKE_CATALOG),
            lake_data=env.get("PERMITMAP_LAKE_DATA", DEFAULT_LAKE_DATA),
            style_url=env.get("PERMITMAP_STYLE_URL", DEFAULT_STYLE_URL),
            geocoder_url=env.get("PERMITMAP_GEOCODER_URL", DEFAULT_GEOCODER_URL),
            host=env.get("PERMITMAP_HOST", "127.0.0.1"),
            port=int(env.get("PERMITMAP_PORT", "8000")),
        )
