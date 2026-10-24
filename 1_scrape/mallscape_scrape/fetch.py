"""Rate-limited, cached HTTP client shared by all scrapers.

Every response body is cached under the run's raw-data directory, so parser
iterations (and validation re-runs on the same day) never re-hit the sites.

Requests go out through curl_cffi with a browser TLS fingerprint rather than a
plain Python client. Cloudflare's bot check (WalterMart, Araneta) challenges
the Python handshake from cloud address ranges whatever the headers say, and
passes the browser one; verified from a GitHub runner 2026-10-13.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
import time
import urllib.parse
from pathlib import Path

from curl_cffi import CurlOpt
from curl_cffi import requests as curl
from curl_cffi.requests.exceptions import (
    ChunkedEncodingError,
    HTTPError,
    IncompleteRead,
    ProxyError,
    RequestException,
    Timeout,
)
from curl_cffi.requests.exceptions import (
    ConnectionError as CurlConnectionError,
)
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from mallscape_core import config

USER_AGENT = config.USER_AGENT


# Greedy to the last @ before the host, as a URL parser splits it, so a
# password holding a raw @ is not cut in half.
_USERINFO = re.compile(r"(\b[a-z][a-z0-9+.-]*://)[^\s/]*@", re.I)


def redact(text: str) -> str:
    """Strip proxy credentials from text bound for logs or the run report.

    The run report is committed to a public repository, and a curl error raised
    while tunnelling can quote the proxy URL. The configured username and
    password go first, in raw, decoded and encoded forms, so they cannot
    survive on their own; then any remaining ``scheme://userinfo@`` is cut to
    ``scheme://***@``.
    """
    if config.PROXY_URL:
        # The whole URL as configured, too: curl quotes it verbatim when it
        # cannot parse it ("Unsupported proxy syntax"), and a URL with an
        # unescaped "/" or "[" in the password parses to no userinfo at all.
        forms = {config.PROXY_URL}
        try:
            parts = urllib.parse.urlsplit(config.PROXY_URL)
            secrets = (parts.password, parts.username)
        except ValueError:  # redacting must never be what fails
            secrets = ()
        for secret in secrets:
            if secret:
                plain = urllib.parse.unquote(secret)
                forms |= {secret, plain, urllib.parse.quote(plain, safe="")}
        # longest first, so a username inside the password cannot shield it
        for form in sorted(forms, key=len, reverse=True):
            text = text.replace(form, "***")
    return _USERINFO.sub(r"\1***@", text)


class FetchError(Exception):
    pass


# Failures to get a whole answer: connection, timeout, proxy, TLS, or a body
# cut off mid-transfer. curl_cffi attaches a Response to every one of these,
# with status 0, or with the real status when the headers arrived before the
# transfer died, so they are recognised by type and never by their status.
_TRANSPORT = (CurlConnectionError, Timeout, ProxyError, IncompleteRead, ChunkedEncodingError)


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, _TRANSPORT):
        return True
    status = exc.response.status_code if isinstance(exc, RequestException) and exc.response is not None else 0
    if status:
        # 403: SM's WAF rate-limits sustained clients; blocks lift after a
        # cooldown, so back off hard and retry rather than dying mid-run
        return status in (403, 429, 500, 502, 503, 504)
    # Any other curl failure with no HTTP answer, such as a read error or an
    # HTTP/2 stream reset. The exact types only: their subclasses are a bad
    # URL, schema, header or redirect loop, which no retry can fix.
    return type(exc) in (RequestException, HTTPError)


class Fetcher:
    def __init__(
        self,
        cache_dir: Path,
        rate: float | None = None,
        timeout: float | None = None,
        headers: dict[str, str] | None = None,
        proxy: str | None = None,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        rate = config.REQUEST_RATE if rate is None else rate
        timeout = config.REQUEST_TIMEOUT if timeout is None else timeout
        if rate <= 0:
            raise ValueError(f"rate must be positive, got {rate}")
        self.min_interval = 1.0 / rate
        self._last_request = 0.0
        self.client = curl.Session(
            impersonate=config.IMPERSONATE,
            headers={
                "User-Agent": USER_AGENT,
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "*/*",
                **(headers or {}),
            },
            timeout=timeout,
            allow_redirects=True,
            # A rotating proxy picks its exit IP per connection, and curl keeps
            # an HTTPS tunnel open across requests: measured 2026-10-24, one
            # session sent every request out of one IP. A new connection per
            # request is what makes every request, and every retry of a 403,
            # leave from a new IP.
            curl_options={CurlOpt.FRESH_CONNECT: 1, CurlOpt.FORBID_REUSE: 1} if proxy else None,
        )
        self.proxy = proxy
        self.requests_made = 0
        self.cache_hits = 0
        self._bypass = False

    @contextlib.contextmanager
    def bypass_cache(self):
        """Serve every request inside the block from the network.

        A cached response is a record of one moment. When a directory comes
        back empty, that moment is exactly what is in doubt, so the retry has
        to reach past the cache or it just re-reads the same emptiness. The
        fresh body replaces the cached one, so the snapshot's raw record still
        matches what was parsed.
        """
        previous, self._bypass = self._bypass, True
        try:
            yield self
        finally:
            self._bypass = previous

    def _cache_path(self, url: str, params: dict | None) -> Path:
        qs = urllib.parse.urlencode(sorted(params.items())) if params else ""
        key = hashlib.md5(f"{url}?{qs}".encode()).hexdigest()[:16]
        parsed = urllib.parse.urlparse(url)
        stem = re.sub(r"[^a-zA-Z0-9._-]+", "_", parsed.netloc + parsed.path).strip("_")
        return self.cache_dir / f"{stem}__{key}"

    def _throttle(self) -> None:
        wait = self.min_interval - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    @retry(
        retry=retry_if_exception(_retryable),
        wait=wait_exponential(multiplier=2, min=5, max=config.RETRY_MAX_WAIT),
        stop=stop_after_attempt(config.RETRY_ATTEMPTS),
        reraise=True,
    )
    def _request(self, url: str, params: dict | None) -> str:
        self._throttle()
        resp = self.client.get(url, params=params, proxy=self.proxy)
        resp.raise_for_status()
        self.requests_made += 1
        return resp.text

    def get_text(self, url: str, params: dict | None = None, force: bool = False) -> str:
        cache = self._cache_path(url, params)
        if cache.exists() and not force and not self._bypass:
            self.cache_hits += 1
            return cache.read_text(encoding="utf-8")
        body = self._request(url, params)
        cache.write_text(body, encoding="utf-8")
        return body

    def get_json(self, url: str, params: dict | None = None, force: bool = False):
        body = self.get_text(url, params, force=force)
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            # poisoned cache entry (e.g. an HTML error page) - drop and refetch once
            cache = self._cache_path(url, params)
            if cache.exists() and not force:
                cache.unlink()
                return self.get_json(url, params, force=True)
            raise FetchError(f"Non-JSON response from {url}: {body[:200]!r}") from exc

    def close(self) -> None:
        self.client.close()
