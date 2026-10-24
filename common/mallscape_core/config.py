"""Runtime configuration, read from the environment with working defaults.

Every operational value lives here rather than being written into a module, so
behaviour can be tuned per environment (a CI run, a slow network, a different
data volume) without editing code. Defaults are the values this project runs
with in practice, so the pipeline works with no environment set at all.

Values are read once at import. Invalid values raise immediately with the
offending variable named, because a silently ignored setting is worse than a
crash: it looks like it worked.

Read `.env.example` for the full list with commentary.
"""

from __future__ import annotations

import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _str(name: str, default: str) -> str:
    return os.environ.get(name, default).strip() or default


def _int(name: str, default: int, *, minimum: int | None = None) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    return value


def _float(name: str, default: float, *, minimum: float | None = None) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    return value


def _path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser().resolve() if raw and raw.strip() else default


# --- where data lives --------------------------------------------------------
DATA_DIR: Path = _path("MALLSCAPE_DATA_DIR", _REPO_ROOT / "data")
SITE_DIR: Path = _path("MALLSCAPE_SITE_DIR", _REPO_ROOT / "4_website" / "site")

# --- how the scraper behaves -------------------------------------------------
# 3 req/s is deliberately conservative. SM's WAF issues a temporary site-wide
# 403 at sustained higher rates; see docs/PITFALLS.md.
REQUEST_RATE: float = _float("MALLSCAPE_REQUEST_RATE", 3.0, minimum=0.1)
REQUEST_TIMEOUT: float = _float("MALLSCAPE_REQUEST_TIMEOUT", 30.0, minimum=1.0)
RETRY_ATTEMPTS: int = _int("MALLSCAPE_RETRY_ATTEMPTS", 8, minimum=1)
RETRY_MAX_WAIT: float = _float("MALLSCAPE_RETRY_MAX_WAIT", 300.0, minimum=1.0)
USER_AGENT: str = _str(
    "MALLSCAPE_USER_AGENT",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 mallscape-research/1.0",
)

# Browser whose TLS handshake requests present (any curl_cffi impersonate
# target). Cloudflare challenges a plain Python handshake from cloud ranges.
IMPERSONATE: str = _str("MALLSCAPE_IMPERSONATE", "chrome")
# A rotating proxy endpoint, http://user:password@host:port, that gives each
# request a new exit IP. It holds credentials, so it is a CI secret, never
# committed. Empty means every request goes direct.
PROXY_URL: str = _str("MALLSCAPE_PROXY_URL", "")
# Only these chains go through it; the rest answer runners directly, and
# residential proxy traffic is billed by the gigabyte.
PROXY_CHAINS: frozenset[str] = frozenset(
    c.strip() for c in _str("MALLSCAPE_PROXY_CHAINS", "sm").split(",") if c.strip()
)

# --- pagination guards -------------------------------------------------------
# Upper bounds only. They exist to turn a runaway loop into a loud failure
# rather than an infinite one, and are far above any real directory size.
MAX_PAGES: int = _int("MALLSCAPE_MAX_PAGES", 500, minimum=1)

# --- website -----------------------------------------------------------------
SITE_PORT: int = _int("MALLSCAPE_SITE_PORT", 3000, minimum=1)
# Identifies the project to the geocoding services below; the page's own links
# are written in the site source, not injected from here.
SITE_REPO_URL: str = _str(
    "MALLSCAPE_SITE_REPO_URL",
    "https://github.com/alpharomercoma/philippine-mall-explorer",
)

# --- geocoding ---------------------------------------------------------------
# Both services are free and need no key. Both ask for an identifying
# User-Agent and, in Nominatim's case, at most one request per second. Those
# are the terms we are using them under, so they are the defaults.
# Overpass is tried in this order and the first full answer wins. The public
# servers are run by volunteers and often at capacity: on 2026-10-24 the main
# one refused every query for hours while maps.mail.ru answered in 86 s. One
# endpoint is a single point of failure for every run that geocodes.
OVERPASS_URLS: tuple[str, ...] = tuple(
    u.strip()
    for u in _str(
        "MALLSCAPE_OVERPASS_URLS",
        "https://overpass-api.de/api/interpreter,"
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    ).split(",")
    if u.strip()
)
NOMINATIM_URL: str = _str("MALLSCAPE_NOMINATIM_URL", "https://nominatim.openstreetmap.org/search")
# The same service read the other way round: what is at this coordinate. Used
# only by `mallscape geocode --verify`, which is how a pin in the sea is found.
NOMINATIM_REVERSE_URL: str = _str(
    "MALLSCAPE_NOMINATIM_REVERSE_URL", "https://nominatim.openstreetmap.org/reverse"
)
GEOCODE_RATE: float = _float("MALLSCAPE_GEOCODE_RATE", 1.0, minimum=0.05)
GEOCODE_OVERPASS_TIMEOUT: float = _float("MALLSCAPE_GEOCODE_OVERPASS_TIMEOUT", 180.0, minimum=10.0)
GEOCODER_USER_AGENT: str = _str(
    "MALLSCAPE_GEOCODER_USER_AGENT", f"mallscape-geocoder/1.0 (+{SITE_REPO_URL})"
)

# Tile server for the map. OpenStreetMap's standard tiles are free and need no
# key. Changing this also means changing the img-src in the page's CSP, which
# the site build checks, so a silent mismatch cannot ship.
TILE_URL: str = _str("MALLSCAPE_TILE_URL", "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
TILE_ATTRIBUTION: str = _str("MALLSCAPE_TILE_ATTRIBUTION", "© OpenStreetMap contributors")
# The page sends no referrer by default, which is right for privacy and wrong
# for tiles: OpenStreetMap's usage policy requires a valid Referer or an
# identifying User-Agent, and a browser cannot set the latter. Without one the
# request is unattributable and gets blocked. This applies to the tile images
# only, and sends the origin without the path.
TILE_REFERRER_POLICY: str = _str(
    "MALLSCAPE_TILE_REFERRER_POLICY", "strict-origin-when-cross-origin"
)
