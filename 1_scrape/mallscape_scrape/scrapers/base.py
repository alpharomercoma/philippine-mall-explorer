"""Chain-scraper interface. Adding a new mall chain = one new subclass."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from mallscape_core.models import Mall, Store
from mallscape_scrape.fetch import Fetcher


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

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)
        print(f"  [warn:{self.chain}] {msg}")

    @abstractmethod
    def discover_malls(self) -> list[Mall]: ...

    @abstractmethod
    def scrape_mall(self, mall: Mall) -> list[Store]: ...

    def scrape_all(self) -> tuple[list[Mall], list[Store]]:
        malls = self.discover_malls()
        print(f"[{self.chain}] discovered {len(malls)} malls")
        stores: list[Store] = []
        for i, mall in enumerate(malls, 1):
            mall_stores = self._scrape_one(mall)
            if mall_stores is None:
                continue
            if not mall_stores:
                # An empty directory is the one result a cached body cannot be
                # trusted for: a mall the operator served in full yesterday and
                # empty today looks identical to a mall that has no directory.
                # Ask the live site once before recording nothing.
                with self.fetcher.bypass_cache():
                    retried = self._scrape_one(mall)
                # A retry of None raised and has already been warned about; an
                # attempt that failed is not evidence of an empty mall.
                if retried:
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
            return None
