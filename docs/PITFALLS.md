# Pitfalls

Every entry here is a bug that actually shipped in this repo and silently lost
or corrupted data. They are recorded because the same mistakes recur when
adding a chain, and because several survived a first audit that pronounced the
data sound.

## The meta-lesson

Re-parsing the same cached input twice and getting identical output proves
**stability, not correctness**. All twelve scrapers passed that check while
four of them were quietly dropping records.

What actually catches this class of bug is comparing a parser's output against
what the *source itself claims to contain*:

- the site's own filter/nav list vs. the malls you produced
- the API's reported `count` vs. the rows you kept
- the raw element count in the cached HTML vs. the parsed row count
- a category page that returns exactly N every time (a cap, not a coincidence)

Write that comparison **before** declaring a chain done.

## Dedupe keys that silently merge distinct records

SM's dedupe keyed on `tenant_slug`. About 1% of SM records ship with an *empty*
slug, so the key silently degraded to the display name and merged genuinely
distinct outlets — two Potato Corners on different floors of the same mall
became one. 238 records lost. Worse, because SM's pagination is not a stable
sort, *which* floor survived varied between fetches.

**Rule:** a dedupe key must include every field that distinguishes two real
records, and must not silently degrade when part of it is missing.

## Deriving a roster from data instead of from the roster

One chain's mall list was derived from its tenant table's branch column. Two
branches were offered by the site's own filter but carried zero tenant rows, so
they never became malls at all: a chain-level undercount invisible in every
report, including the zero-store list.

**Rule:** derive the roster from the site's roster (filter, nav, index), then
attach data to it. Never infer existence from the presence of data.

## Partial unescaping

Starmall's directory sits in a JSON-escaped blob. The parser decoded
`"`, `<`, `>` by hand and stopped there — so `'`
(apostrophe) survived into store names. `brand_key("BAKER'S FAIR")`
produced `baker u0027s fair`, making 21 tenants invisible to the cross-chain
brand matching that is the point of the dataset.

**Rule:** decode the whole escape class (`\\u[0-9a-fA-F]{4}`), never a
hand-picked subset. Corruption that survives into a *key* is worse than
corruption in a display field.

## Cosmetic filters that eat real data

One scraper dropped any name ending in `.` as noise. Real tenants end in
`INC.`, `CORP.`, `ACC.` — 21 of them vanished.

**Rule:** filters must target the specific junk observed, by its own
vocabulary or structure, never by a generic shape that legitimate data shares.
The leasing-form filter in the same module is the right pattern: it matches the
checklist's actual wording.

## Assuming one markup shape

One community mall rendered its tenants as `<br>`-separated text inside a
`<ul>` with zero `<li>` elements. The parser read `<li>` only, produced zero
stores, and the mall was filed as a verified upstream gap. It published 27
tenants.

**Rule:** when a page yields zero rows, prove the page is empty before
recording it as an upstream gap. "Zero" is a claim that needs evidence.

## Documentation that asserts the opposite of reality

`waltermart.py` stated that category pages were the authoritative uncapped
source. In fact every category page caps at 10 tenants, the mall page returns
an identical set, and no `page`/`offset`/`limit`/`show=all` parameter lifts it.
The chain's totals are a **floor**, and the docstring said otherwise.

**Rule:** a docstring claiming completeness needs the same evidence as a
completeness assertion in code. If you cannot cite the test, do not write the
claim.

## Site-reused markup

Robinsons puts parking-rate notices inside `li.store-name`, the same element
used for tenants, so a rates paragraph parsed as a store. One site rendered
its leasing-requirements checklist in the same `div.zn_text_box` as tenant
lists.

**Rule:** container-based selectors need a content-based guard when a site
reuses the container for prose.

## Non-mall properties counted as malls

SM's directory returns 126 properties, of which 20 are SMDC condo retail
podiums, 3 are Sky Ranch amusement parks and 2 are office annexes. Comparing
that 126 against Ayala's 32 overstates SM by a quarter.

**Rule:** classify `property_type` and filter to `mall` before any
chain-vs-chain comparison. Currently only SM is classified — see the open items
in `README.md`.

## Stale and parked domains

Three operators' "official" sites were dead: `megaworldlifestylemalls.com` (no
hyphen) now redirects to an ad/scam domain, `filinvestmalls.com` is a parked
lander, and `shangrilaplaza.com.ph` is for sale.
Search results and old links point at all of them.

**Rule:** confirm the live domain before writing a scraper, and record the dead
ones so nobody re-adds them.

## A validator strict enough to reject the right answer

The geocoder accepted a candidate only if the region derived from its
coordinates equalled the region already recorded for the property. That sounds
conservative. It is not: `derive_region()` falls back to coarse latitude and
longitude boxes, and the Metro Manila box reaches well into Cavite and Bulacan.
So the correct OpenStreetMap feature for "SM City Bacoor" derived to
`metro-manila`, the property was recorded as `south-luzon`, and the exact
name match was thrown away. Twenty-two properties were rejected this way.

Two independent signals, both fallible, must be combined rather than ANDed. The
rule now is that a candidate needs an exact name **or** a corroborating region.
A merely similar name in the wrong region is still rejected.

## A containment rule that matched everything

The same matcher gave a 0.93 score whenever one name's distinctive tokens were
a subset of the other's, in either direction. "SM Store" is a subset of "SM
City Bacoor", so every branch supermarket in the country scored 0.93 against
every SM property. Once the real match was rejected by the bug above, two of
these near-ties 400 km apart made the property "ambiguous".

Containment is only evidence in one direction: the candidate may add tokens to
ours, never drop them. Subset matching also needs a floor on how many tokens
are being matched, or a one-word name matches the whole dataset.

## Output that becomes input

`attach()` skipped any row that already had a coordinate, so the second run
treated its own output as operator-supplied truth. Deleting the registry and
regenerating it therefore preserved 249 coordinates that were no longer in it,
and the committed registry stopped describing the committed data.

A column with two owners needs a field that says which one wrote each value.
The test is now `geo_source == "operator"`, not `lat is not None`, and a row the
registry cannot answer has its coordinate cleared rather than kept.

## Regexes that match the comment above the code

The build rewrites the page's `img-src` so the tile host and the policy
permitting it cannot drift. `img-src [^;]*;` matched the words "img-src" in the
HTML comment explaining the tag, consumed everything up to the first semicolon
of the real policy, and rewrote the comment while leaving the policy untouched.
The substitution reported success because it did replace exactly one match.

Anchor a rewrite to the structure it targets, not to a string that also appears
in prose. Counting substitutions proves something was replaced, not that the
right thing was.

## A filter that means different things in different views

The search box matches brand names in the brand view and property names in the
property view. "Show these on the map" carried the query across, so searching
"uniqlo", then asking to see its 64 malls, produced an empty map: no property
is named Uniqlo. The button had just promised 64.

When one control changes meaning across views, switching views has to decide
explicitly what happens to it. Here the brand focus is the more specific
expression of the same intent, so it replaces the query rather than stacking
with it.

## A foreign key stored as if it were a value

Ortigas publishes `store.type` as `1`, `4`, `9`, and ships the lookup in the
same payload under `props.categories` (`1=Shop, 4=Dining, 9=Bank`). The scraper
stored the integer. Everything downstream saw a number where it expected a
word, mapped it to `unknown`, and 1,075 listings lost a category that was
sitting in the response the whole time.

When a field is small integers and the payload has a sibling collection, it is
a key, not a value. The parser now resolves it and warns on an id the lookup
does not contain.

## A category taxonomy that compares vocabularies, not tenants

Each operator has a catch-all bucket, and they are not the same bucket.
`shopping` held 9,004 listings across six chains, while `fashion` held 159 and
came almost entirely from Filinvest, the only operator that labels apparel
specifically. Bench was `fashion` at Filinvest, `shopping` at SM and `unknown`
at Robinsons: one brand, eleven labels. Filtering by category returned malls
whose operator used that word.

The fix is to categorize the brand rather than the listing: the most specific
label a brand carries anywhere becomes its label everywhere, with `unknown` and
`shopping` explicitly ranked as generic so a real label always wins. That moved
category coverage from 73.8% to 89.5% and gave Robinsons 652 fashion listings
where it had zero.

## Normalizing a name is not resolving an entity

`brand_key` lowercases and folds punctuation. It does not decide that two
names are the same business, so `starbucks` (57 malls) and `starbucks coffee`
(79) were two brands and neither number was Starbucks' reach. Thirty-eight such
pairs existed among brands present in five or more malls.

Resolution is a separate step, and it must be an explicit allow-list. A
similarity threshold high enough to catch `national book store` /
`national bookstore` (0.973) also catches `mi store` / `sm store` (0.875),
which are Xiaomi and The SM Store. The registry now records the merges *and*
the rejected pairs, so the same false positive is not re-argued every time.

## Counting a marker that only exists in a template

Checking whether three WalterMart malls had tenants, a `grep -c wm-store`
returned 90 for each, which looked like a directory we had failed to parse. The
matches were the hidden modal template (`id="wm-store-name"`), present on every
page whether or not it has tenants. Parsing properly returned zero anchors for
those malls and 22 for a control.

Count the thing, not a string that appears near the thing. A control page with
a known answer turns a plausible number into a checkable one.


## A privacy default that broke a third-party dependency

The page sets `no-referrer`, and both the dev server and `vercel.json` send the
same as a header. That is the right default, and it silently disqualified the
map: OpenStreetMap's tile usage policy requires either a valid Referer or a
User-Agent identifying the application, and a browser will not let a page set
the second. Tiles arrived with `referer:` empty, unattributable, and were
refused. Nothing in the page reported it, because a blocked tile looks exactly
like a slow one.

The fix belongs on the element, not the document: Leaflet's `referrerPolicy`
option sets the attribute on each tile image before its `src`, and an
element-level policy outranks both the meta tag and the HTTP header. The
document keeps `no-referrer` for every other destination.

A restrictive default is still a dependency on someone else's terms. When a
third party states what it needs to serve you, check the request it actually
receives rather than the policy you intended to send.


## A z-index scale that was never anyone's to keep private

Opening a filter dropdown over the map showed three of ten operators; the rest
were painted over by tiles. Leaflet numbers its own panes 400 to 700, its
controls 800 and its popups 1000, which is fine as long as something contains
them. Nothing did: `.leaflet-container` is positioned with `z-index: auto`, so
it opens no stacking context, and all of those numbers competed in the root
context against the page's own 20.

The trap is what the DOM says while this is broken. The panel is visible, has a
real bounding box, and wins `elementFromPoint`, because
`.leaflet-tile-container` sets `pointer-events: none` and hit testing reaches
straight through the pixels covering it. A test written the obvious way passes
against the bug. The e2e test therefore screenshots the strip of open panel that
hangs over the map and asserts its dominant colour is the panel's own
background; without the fix it reads OpenStreetMap's water blue.

`isolation: isolate` contains a foreign scale without inventing a z-index for
it. But the first fix then put the stat tiles and the controls on the same
layer, tree order broke the tie in favour of the controls, and the last line of
every stat tooltip disappeared behind the control bar - the same bug, one block
up, introduced by its own fix. Overlays hang downward into the block below, so
the blocks have to be ordered against each other, not merely lifted above the
map.

Borrowed z-index numbers are global until contained. And when a fix reorders
layers, look at every overlay that crosses the boundary it moved, because the
one you were not testing is where it lands.


## A write addressed by index label, on an index that repeats

Scraping one chain carries the others forward, and the carry-forward joined two
frames that each counted from zero. `pd.concat` keeps both, so the index read
`0, 1, 2, ... , 0, 1, 2, 3`. Nothing downstream noticed, because the index is
never written to the CSV and every other check passed: the row count was right,
`(chain, mall_id)` was still unique, and no stage raised.

Then the geocode step walked the frame with `iterrows` and assigned through
`.at[i, "lat"]`. `iterrows` yields index labels, and `.at` writes to *every* row
carrying one. Ortigas has exactly four properties and was scraped last, so its
four coordinates were also written onto the first four SM rows. MOA Square and
S Maison, both in Pasay, were drawn twelve kilometres away in Ortigas; Mall of
Asia Arena Annex and NU MOA had no registry entry at all and inherited
Greenhills and Tiendesitas rather than staying off the map. Their `geo_source`
said `osm` because the last writer set that too, so the row was internally
consistent and wrong. The map showed them clustered with the property whose
coordinate they had taken, which is what a cluster of two is supposed to look
like.

The registry was correct the whole time. Comparing the shipped snapshot against
it found all four in one pass, and nothing else - the check that should have
existed from the start.

**Rule:** address rows, not labels. `reset_index(drop=True)` before any
label-based update, `ignore_index=True` on any concat that feeds one, and a
uniqueness assertion at the snapshot boundary so the condition cannot travel.


## A marker whose only affordance could not be taken

Cluster markers answered a click by zooming to their contents. That is right
until the contents share a coordinate, and several do: three wings of Lucky
Chinatown are one building the operator publishes once, the SMDC strips are
resolved only to their town, and two WalterMart branches matched the same OSM
feature. No zoom separates points at the same point. Clicking stepped closer
until it hit maximum zoom and then did nothing at all, on a bubble still reading
"3" with no way to see what was in it. Seventeen of 292 plotted properties could
not be opened by any route, including the property list beside the map, whose
`focusOn` assumed zooming far enough always frees a point from its cluster.

Two things made it survive. It looks like a rendering artefact rather than a
dead control, so it invites a look at the styling instead of the handler. And
the count is honest - the map is not wrong about there being three - so nothing
in the data flags it.

The fix is to test separability at closest zoom and, when a group fails, open it
as a list rather than offering a zoom that cannot help. Swapping the popup
between the list and one property then detaches the button being clicked, and
Leaflet decides whether a click was the map's by walking up from its target: a
detached target has no path back to the popup, so the click closed the popup it
was navigating. The first e2e test passed against that, because a closing
Leaflet popup stays in the DOM for the length of its fade and an assertion made
immediately after the click reads the list it is about to lose.

**Rule:** a control that cannot do what it offers is worse than no control. And
when asserting on something that animates away, settle first - or the test pins
the transient rather than the outcome.


## The first result that passes is not the best result

Nominatim answers "WalterMart San Jose, Philippines" with three WalterMarts.
The first sits in *barangay* San Jose, in Concepcion, Tarlac. The third is the
San Jose, Nueva Ecija branch, which is the one being asked about. The code took
the first hit that cleared its checks, and the only check that hit had to clear
was `region_agrees` - so a coordinate anywhere in north-luzon, a quarter of the
country, was treated as corroboration. WalterMart San Jose was placed on top of
WalterMart Concepcion, and the map drew the two of them as a cluster of two,
which is exactly what a cluster of two is supposed to look like.

The evidence to tell them apart was in the response and was being thrown away.
`addressdetails=1` returns the address broken into fields, and the difference is
which field carries the word: `quarter: San Jose, town: Concepcion` for the
first, `city: San Jose, state: Nueva Ecija` for the third. So whatever the venue
name does not account for has to be found in the address, and a match on a town
outranks a match on a barangay or a street.

Two details keep that from becoming a new source of missing pins. It ranks, it
never rejects: WalterMart Macapagal is tagged `W.Mall` in Pasay and only its
street carries "Macapagal", and it stays placed. And two properties resolving to
the same building is now reported by name at the end of a refresh - a town
centre is shared by design, a building is not.

**Rule:** when a service returns several answers, rank them on the evidence it
gave you. Accepting the first one that is not obviously wrong is a coin toss
wearing a validation check.


## A fallback ladder that could not reach the bottom

Free-text geocoding falls back through progressively coarser versions of an
address. Two independent faults meant it never arrived.

Every rung had ", Philippines" appended, and scraped addresses routinely end in
"Philippines" already. Nominatim answers a query naming the country twice with
an empty list - not with the sensible reading, and not with an error. So for
those properties every rung asked an unanswerable question and the whole ladder
failed silently. `Makati City, Metro Manila, Philippines, Philippines` returns
nothing; drop one and it returns Makati.

The ladder was also cut at three rungs, counted from the specific end. A
seven-part address spent all three asking about a street corner, a complex and a
barangay, and never got to `1300 Pasay City`, which resolves. The coarse end is
the end that answers, so a limit that trims it is trimming the only rungs with a
job to do. Four properties were unplaced for this reason alone.

The bottom rung is the country by itself, and it resolves happily - to a point
in the Sibuyan Sea. It is inside the bounding box and agrees with any region, so
nothing else in the chain would have stopped it. Ranks below a city are now
refused outright.

**Rule:** a fallback chain is only worth what its last rung returns. Test the
bottom of it, not the top, and check that the bottom is not something that
answers everything.
