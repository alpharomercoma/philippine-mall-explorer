"""WalterMart Community Malls scraper.

The main site (``waltermart.com.ph``) sits behind an sgcaptcha bot challenge,
but the mall subdomain ``malls.waltermart.com.ph`` serves plain HTML with no
challenge:

- ``/malls/`` -> every mall, grouped under region headings, each linking to a
  per-mall slug.
- ``/stores/`` -> every store in the chain (~765), one ``a.wm-store`` anchor
  each, carrying ``data-id`` and ``data-name``. Unlike the per-mall category
  pages, this index is NOT capped.
- ``/stores/<category>/`` -> the same anchors filtered to one category, which
  is the only place a store's category is published.
- ``/api/stores/<id>/`` -> JSON list of the malls carrying that store.

The obvious crawl (``/malls/<slug>/<category>``) caps every category page at
10 tenants server-side, which silently floored this chain at ~31 listings per
property. The routes above surfaced in the Django URLconf that the site's
debug 404 page prints, and together they invert the relation: fetch all
stores once, then ask each store which malls it is in. Roughly 772 requests
rebuilds the complete per-mall tenant lists.

A mall that no store claims is re-checked through the old per-mall category
pages before being recorded as empty: for a mall that small the 10-per-category
cap cannot bite, and the check is per-mall, so the base class retry against
the live site stays meaningful.

Mabalacat, San Pascual and Silang legitimately return zero stores: their
category pages contain only the empty store-detail modal template
(``#wm-store-name`` etc.) and no ``a.wm-store`` tenant anchors at all.
Verified against the live site 2026-07 - an upstream gap, not a selector bug.
"""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from mallscape_core.models import Mall, Store
from mallscape_scrape.scrapers.base import MallChainScraper

BASE = "https://malls.waltermart.com.ph"
CATEGORIES = ("food-choices", "shops", "cybermart", "wellness", "services", "amusement")
REGION_HEADINGS = {
    "metro manila": "metro-manila",
    "north luzon": "north-luzon",
    "central luzon": "north-luzon",
    "south luzon": "south-luzon",
    "visayas": "visayas",
    "mindanao": "mindanao",
}


class WaltermartScraper(MallChainScraper):
    chain = "waltermart"

    _index: dict[str, list[Store]] | None = None
    _mall_meta: dict[str, dict]

    def discover_malls(self) -> list[Mall]:
        html = self.fetcher.get_text(f"{BASE}/malls/")
        tree = HTMLParser(html)
        malls: dict[str, Mall] = {}
        region: str | None = None

        for node in tree.root.traverse(include_text=False):
            if node.tag in ("h1", "h2", "h3", "h4", "h5"):
                label = re.sub(r"\s+", " ", node.text(strip=True)).lower()
                if label in REGION_HEADINGS:
                    region = REGION_HEADINGS[label]
                continue
            if node.tag != "a":
                continue
            href = (node.attributes.get("href") or "").strip()
            # mall links are bare relative slugs like "north-edsa"
            if not href or href.startswith(("http", "/", "#", "mailto")):
                continue
            slug = href.strip("/")
            if slug in malls:
                continue
            name = re.sub(r"\s+", " ", node.text(strip=True)) or slug.replace("-", " ").title()
            malls[slug] = Mall(
                chain=self.chain,
                mall_id=slug,
                mall_name=f"WalterMart {name}" if not name.lower().startswith("walter") else name,
                region=region,
                source_url=f"{BASE}/malls/{slug}/",
            )
        if not malls:
            self.warn("no malls parsed from /malls/ - page structure may have changed")

        # The branches API names every mall a store is in, including malls the
        # /malls/ roster page does not link (Altaraza, 2026-08). Those carry
        # real tenants, so they become properties rather than a silent gap.
        self._store_index()
        for slug, meta in sorted(self._mall_meta.items()):
            if slug in malls:
                continue
            self.warn(f"mall {slug!r} exists only in the branches API - not on /malls/")
            name = re.sub(r"\s+", " ", str(meta.get("name") or slug.replace("-", " ").title()))
            malls[slug] = Mall(
                chain=self.chain,
                mall_id=slug,
                mall_name=f"WalterMart {name}" if not name.lower().startswith("walter") else name,
                region=None,
                address=str(meta.get("address")) if meta.get("address") else None,
                source_url=f"{BASE}/malls/{slug}/",
            )
        return sorted(malls.values(), key=lambda m: m.mall_id)

    def scrape_mall(self, mall: Mall) -> list[Store]:
        stores = self._store_index().get(mall.mall_id, [])
        if stores:
            return stores
        # No store claims this mall. Confirm through the mall's own category
        # pages, which is a live, per-mall observation; for a mall this small
        # the per-category cap cannot truncate anything.
        return self._scrape_mall_pages(mall)

    def _store_index(self) -> dict[str, list[Store]]:
        """``mall slug -> stores``, built once per run from the chain-wide
        store list and each store's branch API."""
        if self._index is not None:
            return self._index

        anchors = self._store_anchors(f"{BASE}/stores/")
        names: dict[str, str] = {}
        for attrs in anchors:
            sid = (attrs.get("data-id") or "").strip()
            name = re.sub(r"\s+", " ", (attrs.get("data-name") or "")).strip()
            if sid and name:
                names.setdefault(sid, name)
        if not names:
            self.warn("/stores/ held no store anchors - page structure may have changed")

        category: dict[str, str] = {}
        for cat in CATEGORIES:
            try:
                for attrs in self._store_anchors(f"{BASE}/stores/{cat}/"):
                    sid = (attrs.get("data-id") or "").strip()
                    if sid:
                        category.setdefault(sid, cat.replace("-", " "))
            except Exception as exc:
                self.warn(f"/stores/{cat}/: {type(exc).__name__}")

        index: dict[str, list[Store]] = {}
        meta: dict[str, dict] = {}
        seen: set[tuple[str, str]] = set()
        failed = 0
        for sid, name in sorted(names.items(), key=lambda kv: int(kv[0])):
            try:
                branches = self.fetcher.get_json(f"{BASE}/api/stores/{sid}/")
            except Exception as exc:
                failed += 1
                self.warn(f"/api/stores/{sid}/ ({name}): {type(exc).__name__}")
                continue
            if not isinstance(branches, list):
                # A 200 that is not a list is a shape change, not an empty
                # store; counting it as success would quietly zero the store.
                failed += 1
                self.warn(f"/api/stores/{sid}/ ({name}): expected a list, got {type(branches).__name__}")
                continue
            for branch in branches:
                slug = (branch.get("slug") or "").strip()
                if not slug or (sid, slug) in seen:
                    # the API repeats some (store, mall) pairs verbatim;
                    # counting them twice inflated the chain by 35 rows
                    continue
                seen.add((sid, slug))
                meta.setdefault(slug, branch)
                index.setdefault(slug, []).append(
                    Store(
                        chain=self.chain,
                        mall_id=slug,
                        store_name_raw=name,
                        category=category.get(sid),
                        source="waltermart-html",
                    )
                )
        if failed > max(3, len(names) // 20):
            # A few flaky stores are survivable; a systemic failure is not.
            # Publishing a snapshot with hundreds of stores quietly missing is
            # worse than no snapshot, and would slip under the 50% collapse
            # guard, so stop the run outright.
            raise SystemExit(
                f"[waltermart] {failed} of {len(names)} store branch lookups "
                "failed; the API has likely changed shape. Not writing a "
                "partial chain."
            )
        if failed:
            self.warn(f"{failed} of {len(names)} store branch lookups failed - counts are low")
        self._index = index
        self._mall_meta = meta
        return index

    def _store_anchors(self, url: str) -> list[dict[str, str | None]]:
        html = self.fetcher.get_text(url)
        return [node.attributes for node in HTMLParser(html).css("a.wm-store")]

    def _scrape_mall_pages(self, mall: Mall) -> list[Store]:
        """The original per-mall crawl, kept as the verification path for
        malls the store index does not mention."""
        page = self.fetcher.get_text(f"{BASE}/malls/{mall.mall_id}/")
        tree = HTMLParser(page)

        # "View All" links name exactly the categories this mall has
        categories = []
        for a in tree.css("a"):
            href = (a.attributes.get("href") or "").strip()
            if "view all" in a.text(strip=True).lower() and href and "/" not in href:
                categories.append(href)
        if not categories:
            categories = list(CATEGORIES)

        by_name: dict[str, Store] = {}
        for cat in dict.fromkeys(categories):
            try:
                html = self.fetcher.get_text(f"{BASE}/malls/{mall.mall_id}/{cat}")
            except Exception as exc:
                self.warn(f"{mall.mall_id}/{cat}: {type(exc).__name__}")
                continue
            for node in HTMLParser(html).css("a.wm-store"):
                attrs = node.attributes
                name = re.sub(r"\s+", " ", (attrs.get("data-name") or "")).strip()
                if not name:
                    continue
                phone = (attrs.get("data-contactnumber") or "").strip()
                by_name.setdefault(
                    name.lower(),
                    Store(
                        chain=self.chain,
                        mall_id=mall.mall_id,
                        store_name_raw=name,
                        category=cat.replace("-", " "),
                        phone=phone if phone not in ("", "-") else None,
                        source="waltermart-html",
                    ),
                )
        return list(by_name.values())
