"""Chain-scraper interface. Adding a new mall chain = one new subclass."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from mallscape_core.models import Mall, Store
from mallscape_scrape.fetch import Fetcher, redact


class MallChainScraper(ABC):
    chain: str  # short id, e.g. "sm"
    # extra HTTP headers this chain's endpoints require (e.g. CORS Origin)
    extra_headers: ClassVar[dict[str, str]] = {}

    def __init__(self, fetcher: Fetcher):
        self.fetcher = fetcher
        self.warnings: list[str] = []
        # Malls that returned nothing twice, the second time straight from the
        # network. Kept apart from `warnings` because emptiness confirmed
        # against the live site is a fact about the operator, while emptiness
        # seen once is only a fact about one request.
        self.confirmed_empty: list[str] = []
        # Malls whose scrape raised, and warnings that mean the operator's
        # site drifted under us (a roster change, a markup change, a partial
        # collection). Both stay warnings in the run report; the weekly check
        # fails on them, so they are kept as data rather than parsed back out
        # of the warning text.
        self.failed: dict[str, str] = {}  # mall_id -> the warning
        self.alerts: list[str] = []

    def warn(self, msg: str) -> None:
        msg = redact(msg)  # warnings go into the committed run report
        self.warnings.append(msg)
        print(f"  [warn:{self.chain}] {msg}")

    def alert(self, msg: str) -> None:
        """A warning the weekly check fails on: something a person has to act on."""
        self.warn(msg)
        self.alerts.append(self.warnings[-1])

    @abstractmethod
    def discover_malls(self) -> list[Mall]: ...

    @abstractmethod
    def scrape_mall(self, mall: Mall) -> list[Store]: ...

    def scrape_all(self) -> tuple[list[Mall], list[Store]]:
        malls = self.discover_malls()
        print(f"[{self.chain}] discovered {len(malls)} malls")
        stores: list[Store] = []
        for i, mall in enumerate(malls, 1):
            first_alerts = len(self.alerts)
            mall_stores = self._scrape_one(mall)
            if mall_stores is None:
                continue
            if not mall_stores:
                attempt_alerts = len(self.alerts)
                # An empty directory is the one result a cached body cannot be
                # trusted for: a mall the operator served in full yesterday and
                # empty today looks identical to a mall that has no directory.
                # Ask the live site once before recording nothing.
                with self.fetcher.bypass_cache():
                    retried = self._scrape_one(mall)
                # A retry of None raised and has already been warned about; an
                # attempt that failed is not evidence of an empty mall.
                if retried:
                    # Whatever the empty attempt alerted on ("served none") was
                    # answered by the live site. It stays a warning, so the
                    # report still shows the retry, but the check is not failed
                    # on a result that was superseded.
                    del self.alerts[first_alerts:attempt_alerts]
                    self.warn(
                        f"{mall.mall_id}: cached response held 0 stores, live site "
                        f"served {len(retried)} - the cached body was stale or partial"
                    )
                    mall_stores = retried
                elif retried is not None:
                    self.confirmed_empty.append(mall.mall_id)
                    self.warn(f"{mall.mall_id}: 0 stores, confirmed against the live site")
            stores.extend(mall_stores)
            print(f"[{self.chain}] {i}/{len(malls)} {mall.mall_id}: {len(mall_stores)} stores")
        return malls, stores

    def _scrape_one(self, mall: Mall) -> list[Store] | None:
        """One mall's tenants, or None if the attempt raised. One mall must
        never kill the run, but a failure must never read as an empty mall
        either, which is why this returns None rather than []."""
        try:
            return self.scrape_mall(mall)
        except Exception as exc:
            self.warn(f"FAILED {mall.mall_id}: {type(exc).__name__}: {exc}")
            self.failed[mall.mall_id] = self.warnings[-1]
            return None
