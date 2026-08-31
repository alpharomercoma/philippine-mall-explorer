# Stage 4: website

**Reads** `1_scrape/malls.parquet` (including its coordinates) and
`2_clean/stores_clean.parquet`.
**Writes** a content hashed bundle into `4_website/site/`.

Run it with `uv run mallscape website`, or `--serve` to open it on
<http://localhost:3000>.

## What is generated and what is not

Only `data-<hash>.json` is generated. `index.html`, `styles.css`, `app.js`,
`map.js` and `vendor/leaflet.*` are checked in and reviewed like any other
source. The build rewrites `index.html` to point at the new bundle, and to
carry the tile URL and the policy that permits it.

The hash is the point: the filename changes whenever the data changes, so a
host can cache the bundle forever and a visitor still gets the newest data. The
previous bundle is deleted, so the deploy directory always holds exactly one.

## Why the bundle is shaped the way it is

303 properties, 10,374 tenant identities and roughly 40,000 brand-to-property edges have to reach
a phone. Three choices keep it near 220 KB compressed: columnar arrays instead
of objects, integer indices into shared dictionaries for every repeated string,
and edges as one flat integer array read in pairs.

## The map

Leaflet, vendored under `site/vendor/`, over OpenStreetMap's standard tiles.
Both are free and need no API key or account, which is why they were chosen
over Mapbox or anything else that starts with a token.

The library is injected on first use rather than loaded with the page, so a
visit that never opens the Map tab does not pay 147 KB for it. `map.js` handles
points, pixels and tiles; `app.js` keeps the data model. Markers cluster on a
fixed pixel grid projected at an explicit zoom, so groups depend on zoom alone
and panning cannot reshuffle them. Circle area, not radius, encodes listing
count.

The map plots exactly what the Properties list would show, so the filters, the
search box and the brand focus all apply. Properties without a coordinate
cannot be drawn and are counted underneath instead. Pins resolved only to a
town are drawn hollow and say so when opened.

Dark mode inverts the raster tiles rather than pulling in a second tile source.
Attribution is rendered as our own DOM, not through Leaflet's control, so the
no-`innerHTML` rule holds across the whole page.

Tile requests carry a referrer even though the page sends none. OpenStreetMap's
usage policy requires a Referer or an identifying User-Agent, and a browser
cannot supply a User-Agent, so a page with `no-referrer` is unattributable and
its tiles get refused. The override is set on the tile images only, via
Leaflet's `referrerPolicy` option, and sends the origin without the path; the
document keeps `no-referrer` for everything else.

`MALLSCAPE_TILE_URL` is the only thing to change to use a different tile
server. The build derives the CSP's `img-src` from it, so the policy and the
request can never disagree, and a template missing `{z}`, `{x}` or `{y}` fails
the build.

## Performance and safety

The list is virtualized. A fixed row height means only the visible window plus
a small overscan is ever in the DOM, so 10,000-plus results cost the same to scroll
as 50. Search is a substring scan over a lowercased array built once at load,
which stays well inside a frame; input is debounced so a fast typist triggers
one pass rather than one per key.

Every value from the data is written with `textContent`. There is no
`innerHTML` anywhere, so a store name can never become markup. That extends
into the map: cluster labels and popups are passed to Leaflet as DOM nodes,
which it appends rather than parses. The page runs under a strict Content
Security Policy with no inline script and exactly one remote origin, the tile
host, carried in the page itself so every host enforces it.

## Hosting

Live at <https://alpharomercoma.github.io/philippine-mall-explorer/>. The
output is a plain directory of static files.

- **Local**: `uv run mallscape website --serve`, which also applies the same
  cache headers as production so local behaviour matches.
- **GitHub Pages**: `.github/workflows/pages.yml` publishes the directory on
  every push to main that touches it, and fails the deploy if `index.html`
  points at a bundle that is not committed. Set the repository's Pages source
  to "GitHub Actions" once. `.github/workflows/rescrape.yml` refreshes the
  data monthly and deploys the same way.
- **Vercel**: `vercel.json` sets the output directory, cache headers, and the
  frame protections that only an HTTP header can carry. It deliberately sends
  no resource CSP: the page's own meta tag carries the full policy, derived
  from the configured tile URL at build time, so the two can never disagree
  about which origins are allowed.
