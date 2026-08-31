# Data reference

The scraped data ships with the repository under `data/snapshots/<date>/`.
`data/raw/` (the HTTP cache) and `data/latest/` (a copy of the newest snapshot)
are not committed - the cache is large, regenerable, and rewritten in place on
re-runs, so it is scratch space rather than provenance.

## Snapshot contents

| file | rows | description |
|---|---|---|
| `malls.{parquet,csv}` | 303 | one row per property |
| `stores.{parquet,csv}` | 40,462 | one row per store listing |
| `brand_presence.*` | - | `(brand_key, chain, mall)` long-format matrix |
| `brand_summary.*` | - | per brand: malls per chain, total, chain count |
| `unique_brands.*` | - | brands present in exactly one mall |
| `mall_summary.*` | - | per mall: store count, brand count, top categories |
| `normalization_review.*` | - | raw-name variants requiring normalization review |
| `breakdown.md` | - | deterministic human-readable report (`mallscape report`) |
| `report.md` | - | validation report from the scrape run |

Parquet and CSV hold identical data. Parquet is what the code reads; CSV is
committed alongside it so the data is diffable and inspectable without pandas.

The four analysis tables are derived from `malls` + `stores` and can be
rebuilt at any time with `mallscape clean --date <date>` and `mallscape report --date <date>`.

## `malls` schema

| column | notes |
|---|---|
| `chain` | operator id (`sm`, `robinsons`, `ayala`, …) |
| `mall_id` | stable slug, unique within a chain |
| `mall_name` | display name as published |
| `region` | `metro-manila` \| `north-luzon` \| `south-luzon` \| `visayas` \| `mindanao`. Always geographic. Only three operators publish one, so the rest are inferred from name and address by `mallscape_core.geo`; resolved for 302 of 303 properties |
| `address` | street address where published |
| `mall_code` | operator-internal id (SM `mallCode`, Ayala numeric id, Contentstack uid) |
| `source_url` | the page or endpoint the data came from |
| `property_type` | `mall` \| `supermarket` \| `residential-retail` \| `amusement-park` \| `office-annex`. **Only SM is classified**; everything else defaults to `mall` |
| `lat`, `lon` | WGS84 decimal degrees, null when unplaced. 294 of 303 are placed |
| `geo_source` | `operator` \| `osm` \| `nominatim`. Who the coordinate came from, in descending order of trust |
| `geo_precision` | `exact` (the building) \| `address` (a street) \| `locality` (a town). The site draws anything below `exact` differently |
| `scraped_at` | date this chain was actually fetched, not the snapshot date |

## `stores` schema

| column | notes |
|---|---|
| `chain`, `mall_id` | join keys to `malls` |
| `store_name_raw` | tenant name exactly as published |
| `category` | operator's own category, lowercased. Vocabularies differ per chain and are not harmonized |
| `floor` | floor/level label. Null for Ayala (their API exposes none) |
| `building` | wing/building. SM only |
| `phone` | where published |
| `source` | which parser produced the row (`sm-api`, `robinsons-drupal`, …) |

`store_name_raw` is deliberately verbatim. Cross-chain matching uses
`brand_key()` from `normalize.py`, applied at analysis time.

## Counting rules

- **Use `property_type == "mall"`** for chain-vs-chain comparison. The raw
  property count overstates SM by 31 non-mall properties: 20 condo retail
  podiums, 5 Savemore and SM Hypermarket grocery stores, 4 amusement parks and
  2 office annexes.
- A row is one *listing*, not one brand. A brand with outlets on two floors is
  two listings in one mall, which is correct for store counts and deduplicated
  automatically for brand presence.
- **Eight properties publish no tenant directory at all** and are therefore not
  in the website bundle: a pin whose popup is empty answers no question a brand
  explorer can ask. Each one is recorded with its evidence and the date it was
  last confirmed in
  [`registry/empty_directories.json`](../1_scrape/mallscape_scrape/registry/empty_directories.json),
  named in every run report, and counted on the page itself ("N properties are
  not shown"). A zero-tenant mall that is *not* in that file is reported as an
  unexplained defect rather than a footnote, because that is what it is: SM
  City La Union published nothing on 2026-07-26 and 199 tenants on 2026-08-30,
  and the difference was the request, not the mall.

## Thin malls are checked, not assumed

Every run names the malls carrying under a quarter of their own chain's median
tenant count, because a directory that half-broke looks like a small mall. As
of 2026-08-30 all fourteen were checked against their source and every one is
the operator's own number:

- **SM** (MarketMall Dasmariñas 16, SM Center Congressional 25, MOA Square 30,
  SM Center Shaw 37, SM Center Antipolo 38, SM By the Bay 39) - each matches the
  `counts` its own API reports for that mall, exactly, except MOA Square at 30
  of 33, which is the usual hidden-tenant shortfall described below.
- **Ayala Serendra** 34 - matches the 34 rows the chain-wide store API returns
  for that mall slug.
- **Robinsons** Cybergate Davao 24 and Luisita 33 - match the `li.store-name`
  count on their own pages. The Plaza is 19 of 20 markers on its VMD page; the
  twentieth is an "RMALLS+ APP NOW!" promo line, correctly excluded.
- **Starmall Talisay** 10 - its page renders 20 gallery items, which are the
  same 10 stores listed twice.
- **Ortigas** The Strip 36 and Tiendesitas 39 - genuinely small formats, a
  dining strip and a bazaar-style market, in a four-property chain whose median
  is dragged up by Greenhills.

## Known accuracy limits

**WalterMart is scraped through its chain-wide store index.** The per-mall
category pages cap at 10 tenants each, so the scraper inverts the crawl: the
uncapped `/stores/` index plus each store's branch API rebuilds the full
per-mall lists (2,254 listings vs the 1,465 the capped pages yielded).

**Ayala listing counts run high.** Their API returns duplicate
`(mall, merchant)` pairs with distinct ids but no distinguishing fields. Brand
presence is unaffected; raw listing counts are inflated by roughly 7%.

**Category vocabularies are not harmonized.** SM's `dining` and Ayala's `dine`
are not merged. Compare categories within a chain, not across.

## Coordinates

`lat`/`lon` do not come from the operator sites except for Ayala and Megaworld,
which publish them. Everything else is resolved once by `mallscape geocode`
against OpenStreetMap and stored in
`1_scrape/mallscape_scrape/registry/mall_coordinates.json`, which is committed.
Rebuilding the snapshot therefore reproduces the same coordinates offline.

Each candidate is validated before it is stored: it must sit inside the
Philippine bounding box, and it must have either an exact name match or a
region consistent with the one already recorded. A candidate that fails is
discarded rather than downgraded, because a confidently wrong pin is worse than
a missing one. 9 properties have no coordinate at all and are reported as such.

## Regenerating

```bash
uv run mallscape scrape --chain all --date 2026-07-26   # re-parses from cache
uv run mallscape clean  --date 2026-07-26
uv run mallscape report --date 2026-07-26
```

With the cache present this is offline and takes seconds. Without it, a full
scrape is roughly 3,000 requests; expect SM's WAF to issue a temporary 403 ban
around 1,500-2,000 requests at 3 req/s, which lifts on its own.
