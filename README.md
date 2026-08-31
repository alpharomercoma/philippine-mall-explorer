# Philippine Mall Explorer

A reproducible dataset of what is inside Philippine malls, and a site for
exploring it.

**304 properties, 41,789 store listings, 10,407 brands, 10 operators.**
**297 properties are placed on a map.** Refreshed monthly by a scheduled
workflow; the page and this table say which snapshot they were built from.

| | |
|---|---|
| Live site | <https://alpharomercoma.github.io/philippine-mall-explorer/> |
| Explore locally | `make dev`, then <http://localhost:3000> |
| Data | [`data/snapshots/2026-08-30/`](data/snapshots/2026-08-30/) |
| Breakdown | [`breakdown.md`](data/snapshots/2026-08-30/3_report/breakdown.md) |
| Design | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Mistakes worth not repeating | [docs/PITFALLS.md](docs/PITFALLS.md) |

## Just run it

```bash
make setup   # dependencies, plus the browser used by end-to-end tests
make all     # stages 2 to 4 over the committed snapshot
make dev     # serve the site on http://localhost:3000
```

The snapshot is committed, so nothing above touches the network. `make scrape`
re-fetches from the operators and is the only slow step.

## Follow it step by step

The pipeline is four stages. Each reads the stage before it and writes only its
own directory, so lineage is visible on disk and any stage can be rerun alone.

```
1_scrape  ->  2_clean  ->  3_report  ->  4_website
```

### 1. Scrape

```bash
uv run mallscape scrape              # every operator
uv run mallscape scrape --chain sm   # or one
```

Writes `data/snapshots/<date>/1_scrape/`: `malls`, `stores`, and a run report
that diffs against the previous snapshot. Store names are recorded verbatim;
nothing interpretive happens here. Full details in [1_scrape/README.md](1_scrape/README.md).

Cold, this is about 3,000 requests over 25 minutes. Responses are cached, so
re-parsing is free and offline.

### 1b. Geocode

```bash
uv run mallscape geocode
uv run mallscape geocode --verify   # and check every pin against what is at it
```

Resolves coordinates for properties the committed registry cannot already
place, and is the only command that needs the network for the map. `--verify`
adds one reverse lookup per placed property and fails if any pin has nothing at
it, which is how a mall drawn in the West Philippine Sea was found; it is the
only check that reads operator-supplied coordinates, which the matcher never
sees. Ordinary runs read
[`registry/mall_coordinates.json`](1_scrape/mallscape_scrape/registry/mall_coordinates.json)
and stay offline, so the map is reproducible. Run this only when a scrape finds
properties that are new.

### 2. Clean

```bash
uv run mallscape clean
```

Also resolves brand spelling variants to one canonical brand using a curated
allow-list, and gives every listing of a brand the most specific category that
brand carries anywhere. Without the first, Starbucks is two brands of 79 and 57
malls; without the second, Bench is `fashion` at Filinvest and `shopping` at SM.

Writes `data/snapshots/<date>/2_clean/stores_clean.*`, which keeps every raw
column and adds normalized ones: display name, brand key, a ten-bucket category
harmonized from 101 operator-specific strings, floor label and numeric level,
phone in `+63` form, and quality flags.

Values that cannot be normalized confidently are kept raw and flagged rather
than coerced. See [2_clean/README.md](2_clean/README.md).

### 3. Report

```bash
uv run mallscape report
```

Writes analysis tables and `breakdown.md`, which is byte identical for the same
snapshot. A diff in the report always means a diff in the data. See
[3_report/README.md](3_report/README.md).

### 4. Website

```bash
uv run mallscape website --serve     # http://localhost:3000
```

Writes a content hashed JSON bundle next to a checked-in page. The list is
virtualized, search is instant, and every value is written as text rather than
markup. The Map tab draws the same result set geographically, so every filter,
the search box and the brand focus apply to both. See
[4_website/README.md](4_website/README.md).

## Operators covered

| operator | properties | malls | listings |
|---|---:|---:|---:|
| SM Supermalls | 126 | 95 | 19,843 |
| Robinsons Malls | 54 | 54 | 8,464 |
| Ayala Malls | 32 | 32 | 5,986 |
| WalterMart | 47 | 47 | 2,220 |
| Megaworld Lifestyle Malls | 26 | 26 | 2,101 |
| Ortigas Land | 4 | 4 | 1,282 |
| Filinvest Malls | 5 | 5 | 953 |
| Fisher Mall | 2 | 2 | 342 |
| Araneta City | 4 | 4 | 319 |
| Starmall | 4 | 4 | 279 |

`malls` excludes non-mall retail such as condo podiums, amusement parks and
office annexes. Compare operators on that column, not on `properties`.

## Coverage is verified, not assumed

Each operator's website is an incomplete view of its own portfolio, so rosters
are checked against corporate disclosures. SM publishes 126 properties but
around 90 malls. Robinsons reported 57 malls while their site lists 54. Ayala's
API exposes 32 of roughly 46 properties, missing Arca South and Evo City
entirely.

Eleven operators were investigated and are deliberately not scraped, including Vista
Malls, CityMall, Gaisano Grand and Puregold. Every gap is recorded as data in
`1_scrape/mallscape_scrape/registry/`, is re-reported on each run, and appears
in `breakdown.md` with the evidence.

## Accuracy limits

- **Ayala listing counts run about 7 percent high.** Its API returns duplicate
  merchant rows with no distinguishing fields. Brand presence is unaffected.

- **7 properties have no coordinate** and are absent from the map, which says
  so under it rather than quietly dropping them. Most are SMDC retail podiums
  that no public gazetteer lists.
- **8 properties publish no tenant directory at all.** Each is recorded with
  its evidence in `registry/empty_directories.json` and left off the site,
  which says how many were withheld. A property whose empty answer is not in
  that registry fails the run report loudly instead of shipping quietly.
- **Roughly 10 percent of listings still have no category.** Robinsons and
  Fisher Mall publish none, and propagation can only fill a gap for a brand
  labelled somewhere else.

## Refreshing on a schedule

`.github/workflows/rescrape.yml` re-scrapes every operator monthly (06:00
Manila time on the 2nd; the cron line in that file is the one place to change
the cadence, and the workflow can also be run on demand from the Actions tab).
It geocodes anything new, verifies every pin, rebuilds the data and the site,
runs the full checks, commits the new snapshot to main, and deploys to GitHub
Pages. A failed month publishes nothing: the site keeps serving the last good
snapshot, and the failure is visible in Actions.

Two guards keep an unattended run honest. A chain that loses more than half
its listings against the previous snapshot stops the run, because that is
usually the operator's site breaking rather than the malls emptying
(`MALLSCAPE_ACCEPT_COLLAPSE` accepts a real shrink for one run). And a mall
that returns zero tenants is re-asked against the live site before being
believed.

The page says which snapshot it was built from, and its footer links the CSV,
Parquet and JSON for exactly that snapshot, so downstream consumers can pin a
month and reprocess it.

## Configuration

Every operational value reads from the environment with a working default, so
the pipeline runs with nothing set. Copy `.env.example` only to change
something. An invalid value fails immediately and names itself rather than
being ignored.

## Tests

```bash
make check   # lint, unit, integration
make e2e     # drives the built site in a real browser
```

| layer | what it protects |
|---|---|
| lint | style and unused imports, via ruff |
| unit | parsers against frozen fixtures, with exact expected counts |
| integration | the handoff between stages, including carry-forward and schema |
| end to end | the built site: bundle validity, search, virtualization, mobile layout, map plotting and filtering, no script errors |

## Etiquette

Rate limited to 3 requests per second with backoff and an identifying user
agent, and every response cached so parser work never re-hits a site.

## Open items

- `region` is null for one property, SMBY Amusement Park, which publishes
  neither an address nor a resolvable coordinate.
- `property_type` is classified only for SM, so a non-mall property from
  another operator still compares against SM malls as a peer.
- Gaisano Capital, LCC Group and NCCC are blocked or unconfirmed rather than
  proven directory-less. Each needs a browser session.
