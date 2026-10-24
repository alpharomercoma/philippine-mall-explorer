"""Araneta City scraper (Araneta Group, Cubao).

``aranetacity.com`` was rebuilt in October 2026 (the old ``/shopping/<slug>``
pages now 404). Tenants are split across three server-rendered directories,
each filtered by building and paginated 30 to a page (verified 2026-10-21):

- ``GET /shopping?building=<slug>&page=<n>``
- ``GET /dining?building=<slug>&page=<n>``
- ``GET /services?building=<slug>&page=<n>``

Each tenant is one card::

    <article class="est-card">
      ... <h3 class="est-card-title"><a href="/establishment/530">7-Eleven</a></h3>
      <div class="est-card-location"><i ...></i><span> GF, Ali Mall </span></div>
    </article>

The location is ``<floor>, <building name>``; some carry only the building.
A page past the last one renders no cards, which is how pagination ends.

Gotchas:

- An unrecognised ``building`` value is ignored rather than rejected: the
  page then lists every establishment in the complex. A renamed slug would
  silently hand one mall hundreds of other venues' tenants, so every card's
  building is checked against the mall being scraped.
- The old single-page directory matched only today's ``/shopping``. Dining
  and services were never captured before this rewrite, which is why the
  chain's listing count roughly doubled with it.

Araneta City is one operator running several adjacent venues. ``/malls`` is
the operator's own list of its four malls, and those are what is scraped. The
other buildings in the directory filter (towers, markets, arcades, hotels,
residences) are recorded in ``registry/araneta_coverage.json``.
"""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from mallscape_core import config
from mallscape_core.models import Mall, Store
from mallscape_scrape.fetch import FetchError
from mallscape_scrape.scrapers.base import MallChainScraper

BASE = "https://aranetacity.com"
DIRECTORIES = ("shopping", "dining", "services")
MAX_PAGES = config.MAX_PAGES  # loop guard; the largest directory is 4 pages

# site slug -> (mall_id, display name, address). The mall_ids predate the
# redesign and key the coordinate registry and every earlier snapshot, so
# they stay put even where the site's slug changed (gateway-mall-1).
MALLS = {
    "gateway-mall-1": (
        "gateway-mall", "Gateway Mall 1", "General Roxas Ave., Araneta City, Cubao, Quezon City",
    ),
    "gateway-mall-2": ("gateway-mall-2", "Gateway Mall 2", "Araneta City, Cubao, Quezon City"),
    "ali-mall": ("ali-mall", "Ali Mall", "General Roxas Ave., Araneta City, Cubao, Quezon City"),
    "farmers-plaza": (
        "farmers-plaza", "Farmers Plaza", "General Araneta St., Araneta City, Cubao, Quezon City",
    ),
}


def _text(node) -> str:
    return re.sub(r"\s+", " ", node.text(strip=True)).strip() if node else ""


def parse_cards(html: str) -> list[tuple[str, str, str]]:
    """(establishment id, name, location) for each card on a directory page."""
    cards = []
    for card in HTMLParser(html).css("article.est-card"):
        link = card.css_first("h3.est-card-title a")
        if link is None:
            continue
        match = re.search(r"/establishment/(\d+)", link.attributes.get("href") or "")
        cards.append((
            match.group(1) if match else "",
            _text(link),
            _text(card.css_first(".est-card-location span")),
        ))
    return cards


def split_location(location: str) -> tuple[str | None, str]:
    """``"Food Gallery, Ali Mall"`` -> ``("Food Gallery", "Ali Mall")``.

    Split on the last comma: the building is always last, and a floor name
    could itself hold a comma. A bare building name has no floor.
    """
    floor, sep, building = location.rpartition(",")
    if not sep:
        return None, location.strip()
    return floor.strip() or None, building.strip()


class AranetaScraper(MallChainScraper):
    chain = "araneta"

    def discover_malls(self) -> list[Mall]:
        self._check_roster()
        return [
            Mall(
                chain=self.chain,
                mall_id=mall_id,
                mall_name=name,
                region="metro-manila",
                address=address,
                source_url=f"{BASE}/shopping?building={slug}",
                extra={"slug": slug, "building": name},
            )
            for slug, (mall_id, name, address) in MALLS.items()
        ]

    def _check_roster(self) -> None:
        """The four malls are hardcoded so their ids and addresses stay
        stable. Check them against the operator's own mall list each run, so
        a new mall or a renamed slug is flagged rather than silently missed."""
        try:
            html = self.fetcher.get_text(f"{BASE}/malls")
        except Exception as exc:
            self.alert(f"could not verify mall roster ({type(exc).__name__})")
            return
        live = set(re.findall(r'href="/shopping\?building=([a-z0-9-]+)"', html))
        if not live:
            self.alert("roster check found no /shopping?building= links on /malls - markup may have changed")
            return
        new, gone = sorted(live - set(MALLS)), sorted(set(MALLS) - live)
        if new:
            self.alert(f"NEW Araneta mall(s) on /malls not scraped: {new} - add to MALLS in araneta.py")
        if gone:
            self.alert(f"mall(s) no longer on /malls: {gone} - slug renamed or mall delisted")

    def scrape_mall(self, mall: Mall) -> list[Store]:
        slug, building = mall.extra["slug"], mall.extra["building"]
        stores: list[Store] = []
        seen: set[str] = set()
        for directory in DIRECTORIES:
            for page in range(1, MAX_PAGES + 1):
                html = self.fetcher.get_text(
                    f"{BASE}/{directory}", {"building": slug, "page": page}
                )
                cards = parse_cards(html)
                if not cards:
                    break
                elsewhere = [c for c in cards if split_location(c[2])[1] != building]
                if len(elsewhere) >= len(cards) - len(elsewhere):
                    raise FetchError(
                        f"{mall.mall_id}: building filter ignored on /{directory} page {page} - "
                        f"{len(elsewhere)} of {len(cards)} cards are in other venues"
                    )
                if elsewhere:
                    self.warn(
                        f"{mall.mall_id}: skipped {len(elsewhere)} /{directory} card(s) located "
                        f"elsewhere: {sorted({split_location(c[2])[1] for c in elsewhere})}"
                    )
                for est_id, name, location in cards:
                    floor, where = split_location(location)
                    if where != building or not name:
                        continue
                    # one establishment, one row: guards against a tenant
                    # being filed under two directories
                    if est_id and est_id in seen:
                        self.warn(f"{mall.mall_id}: establishment {est_id} listed twice ({name})")
                        continue
                    seen.add(est_id)
                    # No dedupe by name: a brand with outlets on two floors is
                    # two real tenants, and brand analysis dedupes per mall.
                    stores.append(
                        Store(
                            chain=self.chain,
                            mall_id=mall.mall_id,
                            store_name_raw=name,
                            category=directory,
                            floor=floor,
                            source="araneta-html",
                        )
                    )
            else:
                raise FetchError(f"{mall.mall_id}: /{directory} ran past {MAX_PAGES} pages")
        if not stores:
            self.alert(f"{mall.mall_id}: no est-card tenants found - markup may have changed")
        return stores
