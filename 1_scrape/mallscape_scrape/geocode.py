"""Coordinates for every property, resolved once and committed to a registry.

The map needs a latitude and longitude per property, but geocoding is a network
call against a third-party service, and a pipeline that has to hit the network
to redraw a map is neither reproducible nor polite. So coordinates are treated
the way the coverage registries already are: as data.

Three sources, in descending order of trust:

``operator``
    The chain's own API publishes the coordinate. Ayala and Megaworld do. This
    is the mall as its owner locates it, and nothing outranks it - except a
    registry entry that says in writing why the operator is wrong, which is
    what `corrects_operator` is for. Ayala publishes a longitude for Serin that
    is 76 km west of its own address, in the sea.
``osm``
    A named ``shop=mall`` feature in OpenStreetMap, matched by name. One
    Overpass query returns every retail feature in the Philippines, so this
    resolves most of the remainder in a single request rather than hundreds.
``nominatim``
    Free-text geocoding of name plus address, one request per property at the
    1 req/s the usage policy allows. Last resort, and the only tier that can
    land on a street or a town rather than on the building.

Every candidate is validated before it is accepted: it must fall inside the
Philippine bounding box, something the query asked for must appear in the
answer, and where that something is only a street or a barangay the region must
agree as well. A candidate that fails is discarded rather than downgraded,
because a confidently wrong pin is worse on a map than a missing one.

The last check is the coordinate itself. Where a property came with an address,
whatever is at the chosen coordinate is looked up and has to be somewhere that
address mentions; this is what tells two buildings of the same name apart, and
`mallscape geocode --verify` runs it over every placed property including the
operator tier.

Results land in ``registry/mall_coordinates.json``, which is committed. Normal
runs read it and never touch the network. ``mallscape geocode`` is the only
thing that refreshes it, and it only looks up properties the registry does not
already answer.
"""

from __future__ import annotations

import difflib
import json
import math
import re
import unicodedata
from pathlib import Path

import pandas as pd

from mallscape_core import config
from mallscape_core.geo import derive_region, in_bounds
from mallscape_scrape.fetch import Fetcher

REGISTRY = Path(__file__).parent / "registry" / "mall_coordinates.json"
SCHEMA_VERSION = 1

GEO_COLUMNS = ("lat", "lon", "geo_source", "geo_precision")

# Words that appear in so many mall names that they carry no signal when
# deciding whether two names denote the same building.
_GENERIC = frozenset({
    "mall", "malls", "the", "shopping", "center", "centre", "complex",
    "supermarket", "hypermarket", "department", "store", "branch", "inc",
})

# Structural words in an address: they say what kind of thing a component is,
# never which one. `supported` has to ignore them, because "Pasig City" and
# "Quezon City" share a word and sharing it is not agreement. That single word
# is what let a Quezon City node keep the pin for a Pasig property.
_ADDRESS_FILLER = frozenset({
    "city", "cities", "municipality", "province", "district", "zone", "region",
    "street", "st", "avenue", "ave", "road", "rd", "boulevard", "blvd",
    "highway", "hwy", "corner", "cor", "barangay", "brgy", "bgy", "poblacion",
    "sitio", "purok", "subdivision", "subd", "compound", "phase", "block",
    "floor", "level", "bldg", "building", "tower", "annex", "wing", "philippines",
})

# Words that appear in place names all over the country and so agree by
# accident: honorifics, articles, and bare numbers. "San Jose del Monte,
# Bulacan" and "San Fernando, Pampanga" share "san" and "del" and nothing else,
# and one shared word is all `supported` asks for.
_WEAK_TOKENS = frozenset({
    "san", "santa", "santo", "sta", "sto", "sn", "de", "del", "dela", "las",
    "los", "la", "el", "new", "old", "upper", "lower", "poblacion",
})

# A name match this close is a candidate at all; below it, nothing is considered.
_RATIO_ACCEPT = 0.90
# A name this close is treated as certain, which lets it outrank a disagreeing
# region. See best_match for why that is the right way round.
_RATIO_CERTAIN = 1.0
# Two candidates scoring within this of each other, far apart, are ambiguous.
_RATIO_TIE = 0.02
_TIE_DISTANCE_KM = 5.0

# Where a match in Nominatim's address breakdown places a name. A town or a
# province identifies a branch; a barangay or a street only narrows it down,
# and several towns have a barangay by the same name as another town.
_SETTLEMENT_KEYS = ("city", "town", "municipality", "village", "hamlet", "county", "state")
_LOCAL_KEYS = ("suburb", "quarter", "neighbourhood", "city_district", "borough", "road")

# Nominatim's place_rank rises with specificity: 4 is a country, 8 a region, 12
# a city, 16 a town, 22 upwards a street or a building. Below a city there is
# no sense in which the answer is where the mall is, and "Philippines" resolves
# happily to a point in the Sibuyan Sea.
_MIN_PLACE_RANK = 10

# Overpass returns every named retail feature in the country in one call.
_OVERPASS_QUERY = """
[out:json][timeout:{timeout}];
area["ISO3166-1"="PH"][admin_level=2]->.ph;
(
  nwr["shop"="mall"]["name"](area.ph);
  nwr["shop"="department_store"]["name"](area.ph);
  nwr["shop"="supermarket"]["name"](area.ph);
);
out center tags;
"""


# --------------------------------------------------------------------------
# registry
# --------------------------------------------------------------------------


def key_of(chain: str, mall_id: str) -> str:
    return f"{chain}:{mall_id}"


def load() -> dict[str, dict]:
    """Committed coordinates, keyed ``chain:mall_id``. Empty if never resolved."""
    if not REGISTRY.exists():
        return {}
    doc = json.loads(REGISTRY.read_text())
    if doc.get("schema") != SCHEMA_VERSION:
        raise SystemExit(
            f"{REGISTRY.name} has schema {doc.get('schema')}, expected "
            f"{SCHEMA_VERSION}. Delete it and rerun `mallscape geocode`."
        )
    return doc["entries"]


def save(entries: dict[str, dict]) -> None:
    """Write the registry with sorted keys, so a refresh produces a readable diff."""
    doc = {
        "schema": SCHEMA_VERSION,
        "note": (
            "Coordinates per chain:mall_id. Generated by `mallscape geocode`; "
            "committed so normal runs need no network. See 1_scrape/geocode.py."
        ),
        "entries": {k: entries[k] for k in sorted(entries)},
    }
    REGISTRY.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")


def usable(entry: dict | None) -> bool:
    """Whether a registry entry carries coordinates that are actually numbers.

    `attach` coerces its output with `errors="coerce"`, so a lat of "" or null
    lands as NaN with `geo_source` and `geo_precision` still saying `osm/exact`.
    On an operator-placed row an entry like that would replace a good
    coordinate with a hole wearing a confident label, which is the one outcome
    the override was built to prevent.
    """
    if not entry:
        return False
    return coords_of(entry) is not None


def is_operator_placed(row) -> bool:
    """Whether the chain's own API supplied this coordinate.

    This is the line between the two owners of the column. Operator
    coordinates arrive with the scrape and nothing else may touch them; every
    other coordinate belongs to the registry, which therefore also gets to
    remove one. Testing the source rather than "is lat set?" is what makes
    attach idempotent: run it twice and the second run cannot mistake its own
    output for input.
    """
    return row.get("geo_source") == "operator" and pd.notna(row.get("lat"))


def attach(malls: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Set coordinates from the registry wherever the operator supplied none.

    Returns the frame plus the keys still unplaceable, which the caller reports
    rather than swallows: a property missing from the map is a coverage fact.
    """
    # Reset before writing anything. `iterrows` yields index labels, and
    # `.at[label]` writes to every row carrying that label, so on a frame whose
    # index repeats one property's coordinate lands on another's row without a
    # word of complaint. Carrying a chain forward concatenates two frames that
    # each count from zero, which is exactly that frame. See the pipeline's
    # `ignore_index`: this is the second lock on the same door, because attach
    # is what actually does the damage.
    malls = malls.copy().reset_index(drop=True)
    for column in GEO_COLUMNS:
        if column not in malls.columns:
            malls[column] = None
    entries = load()

    missing: list[str] = []
    corrected: list[str] = []
    for i, row in malls.iterrows():
        entry = entries.get(key_of(row["chain"], row["mall_id"]))
        if is_operator_placed(row):
            # "Nothing can beat the operator" held until Ayala published a
            # longitude 0.7 degrees west of its own address, which put Ayala
            # Malls Serin in the West Philippine Sea. An operator can be wrong,
            # so the registry may say so - but only in writing, per property,
            # with the evidence in `corrects_operator`.
            if not (entry and entry.get("corrects_operator")):
                continue
            if not usable(entry):
                print(
                    f"[geocode] ignoring the override for "
                    f"{key_of(row['chain'], row['mall_id'])}: its coordinates are not numbers"
                )
                continue
            corrected.append(key_of(row["chain"], row["mall_id"]))
        hit = entry if usable(entry) else None
        if hit is None:
            # Clear rather than keep: a coordinate the registry no longer
            # vouches for is not evidence, and leaving it would make the
            # snapshot depend on the order runs happened in.
            for column in GEO_COLUMNS:
                malls.at[i, column] = None
            missing.append(key_of(row["chain"], row["mall_id"]))
            continue
        malls.at[i, "lat"] = hit["lat"]
        malls.at[i, "lon"] = hit["lon"]
        malls.at[i, "geo_source"] = hit["source"]
        malls.at[i, "geo_precision"] = hit["precision"]

    malls["lat"] = pd.to_numeric(malls["lat"], errors="coerce")
    malls["lon"] = pd.to_numeric(malls["lon"], errors="coerce")
    if corrected:
        print(f"[geocode] overrode {len(corrected)} operator coordinate(s): {sorted(corrected)}")
    return malls, missing


# --------------------------------------------------------------------------
# matching
# --------------------------------------------------------------------------


def normalize_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name))
    text = text.encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def core_tokens(name: str) -> frozenset[str]:
    """Name tokens with the words every mall shares removed."""
    return frozenset(t for t in normalize_name(name).split() if t not in _GENERIC)


def distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance, used only to tell near-ties apart."""
    radius = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(h))


def region_agrees(region: str | None, lat: float, lon: float) -> bool:
    """Whether a coordinate lands in the region the property is recorded in.

    This is corroboration, not proof. `derive_region` falls back to coarse
    latitude and longitude boxes, and the Metro Manila box reaches into Cavite
    and Bulacan, so a correct pin for a Cavite mall disagrees with its
    "south-luzon" bucket. Callers weigh this against the name rather than
    treating a disagreement as fatal. Properties with no recorded region cannot
    be cross-checked and so pass.
    """
    if not region:
        return True
    return derive_region("", lat, lon) == region


def score(mall_name: str, candidate_name: str) -> float:
    """Similarity in [0, 1]. Exact core-token equality is treated as certain,
    because "SM City Cebu" and "SM Cebu" are the same building described twice."""
    a, b = normalize_name(mall_name), normalize_name(candidate_name)
    if a == b:
        return 1.0
    ta, tb = core_tokens(mall_name), core_tokens(candidate_name)
    if ta and ta == tb:
        return 1.0
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    # Containment counts only when the candidate carries every distinctive
    # token we have and adds at most a couple ("SM City Baguio" inside "SM City
    # Baguio Annex"). The other direction is not evidence: a candidate merely
    # named "SM Store" shares all of its tokens with every SM property in the
    # country, and treating that as a 0.93 match let branch supermarkets
    # outrank the actual mall.
    if len(ta) >= 2 and ta < tb and len(tb - ta) <= 2:
        ratio = max(ratio, 0.93)
    return ratio


def best_match(
    mall_name: str,
    region: str | None,
    candidates: list[dict],
) -> tuple[dict | None, str]:
    """Pick one OSM candidate, or explain why none was picked.

    Returns ``(candidate, reason)``. ``reason`` is empty on success and is a
    short diagnostic otherwise, so the refresh report says what happened rather
    than only that a lookup failed.
    """
    scored = []
    for cand in candidates:
        if not in_bounds(cand["lat"], cand["lon"]):
            continue
        value = max(score(mall_name, name) for name in cand["names"])
        if value >= _RATIO_ACCEPT:
            scored.append((value, cand))
    if not scored:
        return None, "no name match"

    scored.sort(key=lambda pair: (-pair[0], pair[1]["id"]))

    # Two independent kinds of evidence: the name, and the region the
    # coordinate falls in. Either one on its own has a known failure mode, so
    # accept a candidate that has both, or one that has an exact name. A merely
    # similar name in the wrong region is what gets thrown away.
    pool = [(v, c) for v, c in scored if region_agrees(region, c["lat"], c["lon"])]
    if not pool:
        pool = [(v, c) for v, c in scored if v >= _RATIO_CERTAIN]
    if not pool:
        return None, f"matched {len(scored)} feature(s), none in {region}"

    top_score, top = pool[0]
    for value, other in pool[1:]:
        if top_score - value > _RATIO_TIE:
            break
        if distance_km((top["lat"], top["lon"]), (other["lat"], other["lon"])) > _TIE_DISTANCE_KM:
            return None, "ambiguous: two equally good features far apart"
    return top, ""


# --------------------------------------------------------------------------
# sources
# --------------------------------------------------------------------------


def fetch_osm_features(fetcher: Fetcher) -> list[dict]:
    """Every named retail feature in the Philippines, from one Overpass call."""
    query = _OVERPASS_QUERY.format(timeout=int(config.GEOCODE_OVERPASS_TIMEOUT))
    payload = fetcher.get_json(config.OVERPASS_URL, {"data": query})
    features = []
    for element in payload.get("elements", []):
        tags = element.get("tags") or {}
        center = element if element.get("type") == "node" else element.get("center") or {}
        lat, lon = center.get("lat"), center.get("lon")
        if lat is None or lon is None:
            continue
        names = [
            tags[k]
            for k in ("name", "name:en", "alt_name", "official_name", "short_name")
            if tags.get(k)
        ]
        if not names:
            continue
        features.append({
            "id": f"{element['type']}/{element['id']}",
            "names": names,
            "lat": float(lat),
            "lon": float(lon),
        })
    if not features:
        raise SystemExit(
            f"Overpass returned no retail features from {config.OVERPASS_URL}. "
            f"The query or the endpoint changed; fix it rather than shipping an empty map."
        )
    return features


def text_of(value: object) -> str | None:
    """A usable string, or None. Addresses arrive from pandas as NaN floats,
    which are truthy: without this, queries went out reading ", nan,"."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).strip()
    return text if text and text.lower() != "nan" else None


def address_tails(address: str, limit: int = 6) -> list[str]:
    """Progressively coarser versions of an address, most specific first.

    Philippine addresses are written most specific first, so dropping leading
    components trades precision for the chance of a hit. Nominatim returns
    nothing at all for "Katipunan Avenue corner Escalar Street, Loyola Heights,
    Quezon City" because "corner Escalar Street" is not a street it knows, and
    everything for "Loyola Heights, Quezon City".

    The coarse end is the end that answers, so the limit has to be generous
    enough to reach the town. At three, a seven-part address asked three
    questions about street corners and a subdivision, and never asked about
    Pasay. The rungs are still tried most specific first, so a longer ladder
    costs requests only for a property nothing else could place.

    The country on its own is dropped rather than asked: it resolves, to the
    centroid of the archipelago, which is a worse answer than none.
    """
    parts = [p.strip() for p in address.split(",") if p.strip()]
    tails = [", ".join(parts[i:]) for i in range(1, len(parts))]
    return [t for t in tails if normalize_name(t) != "philippines"][:limit]


def with_country(query: str) -> str:
    """Append the country unless the text already ends with it.

    Nominatim answers a free-form query that names the country twice with an
    empty list, not with the answer to the sensible reading. Scraped addresses
    routinely end in "Philippines", so appending it unconditionally silently
    disabled every coarser fallback for those properties: the ladder ran to the
    bottom asking questions that could not be answered.
    """
    return query if normalize_name(query).endswith("philippines") else f"{query}, Philippines"


def place_match(name: str, hit: dict) -> int:
    """How well the hit's address explains the part of the name its own name did not.

    A branch is usually named for where it is, and the venue name rarely repeats
    that: OpenStreetMap calls them all "WalterMart". So whatever is left of the
    property name after the venue name is accounted for has to be found in the
    address, and *where* it is found is the whole point. 2 for a town or
    province, 1 for a barangay or a street, 0 for nowhere.

    This ranks candidates; it never rejects one. A name the address cannot
    explain at all is still placed if it passed the checks that came before.

    Known limit: a token overlap, not a name match. "San Jose del Monte" scores
    a settlement match for "WalterMart San Jose", so it would outrank a correct
    candidate whose only evidence is its street. Tightening this to an exact
    match is not the fix - the tokens are unioned across every settlement field,
    so the genuinely correct hit carries its barangay and province too and would
    stop matching as well. Telling those apart needs per-field comparison, which
    is more machinery than the one collision this was built for justifies. No
    property in the current data is placed wrongly by it; a future one could be.
    """
    ours = core_tokens(name)
    if not ours:
        # Nothing distinctive to place. An empty leftover below means the venue
        # name accounted for everything; here it means there was nothing to
        # account for, which is the absence of evidence rather than the best of
        # it, and must not outrank a candidate the address actually explains.
        return 0
    leftover = ours - core_tokens(hit.get("name") or "")
    if not leftover:
        return 2                       # the venue name accounted for all of it
    address = hit.get("address") or {}
    for level, keys in ((2, _SETTLEMENT_KEYS), (1, _LOCAL_KEYS)):
        tokens: set[str] = set()
        for key in keys:
            tokens |= set(normalize_name(address.get(key) or "").split())
        if leftover & tokens:
            return level
    return 0


def hit_tokens(hit: dict, place_only: bool = False) -> set[str]:
    """Every word the hit uses to describe itself and where it is.

    `place_only` keeps the settlement and street fields and drops everything
    that names the feature. A check run *after* a match must not read the name
    back: reverse-geocoding the coordinate we just picked returns the very
    feature we picked it from, and Nominatim repeats that feature's name inside
    the address breakdown too, under a key named for its class ("shop": "The
    Strip Mall"). Both routes let a Quezon City node corroborate itself as a
    Pasig property. Where it is has to answer on its own.
    """
    address = hit.get("address") or {}
    if place_only:
        parts = [address.get(k) for k in (*_SETTLEMENT_KEYS, *_LOCAL_KEYS)]
    else:
        parts = [hit.get("name"), *address.values()]
    text = " ".join(str(v) for v in parts if v)
    return set(normalize_name(text).split()) - _GENERIC


def distinctive(tokens: set[str]) -> set[str]:
    """The words in a place name that identify *which* place it is."""
    return {t for t in tokens - _ADDRESS_FILLER - _WEAK_TOKENS if not t.isdigit()}


def supported(query: str, hit: dict, place_only: bool = False) -> bool:
    """Whether the hit repeats anything distinctive from what we asked for.

    Being inside the right region is not evidence. A region is a quarter of the
    country, so "in the right region" was satisfied by the Urdaneta Philippines
    Temple in Pangasinan for a query about WalterMart Balanga in Bataan, and by
    Robinsons Starmills in Pampanga for Robinsons Gapan in Nueva Ecija. Both
    were recorded as confident pins, 140 km and 40 km from the property.

    So a candidate no better than "somewhere in Luzon" is dropped rather than
    downgraded: the query has to appear in the answer, either in the venue's own
    name or somewhere in its address. Any single distinctive word does, because
    a query is usually a brand plus a town and either one carries real
    information - but only a *distinctive* one, or "Pasig City" and "Quezon
    City" agree, and so do San Fernando and San Jose del Monte.

    When that filtering empties either side it has taken the answer with it: a
    property whose whole name is a filler word (The Block, a barangay called
    Zone) has nothing left to match on. There the unfiltered words are all
    there is, so they are what gets compared.
    """
    ours = set(normalize_name(query).split()) - _GENERIC
    if not ours:
        return False
    theirs = hit_tokens(hit, place_only)
    strong_ours, strong_theirs = distinctive(ours), distinctive(theirs)
    if strong_ours and strong_theirs:
        return bool(strong_ours & strong_theirs)
    return bool((ours - {"philippines"}) & theirs)


def coords_of(hit: dict) -> tuple[float, float] | None:
    """The hit's coordinate, or None when it is absent or not a number.

    Parsed before anything validates the hit, so a single malformed pair used to
    raise and end the run for the same reason a malformed rank did. See
    `place_rank_of`: one unusable hit is worth one skipped hit, never a lost
    refresh.
    """
    try:
        return float(hit["lat"]), float(hit["lon"])
    except (KeyError, TypeError, ValueError):
        return None


def place_rank_of(hit: dict) -> int | None:
    """Nominatim's specificity rank, or None when it is missing or unusable.

    Read for every candidate rather than only the chosen one, so a single hit
    carrying null here used to raise and end the run. A refresh writes the
    registry once at the end, so that discarded every property resolved before
    it. One unusable hit is worth one skipped hit.
    """
    try:
        return int(hit.get("place_rank"))
    except (TypeError, ValueError):
        return None


def cap_precision(precision: str, cap: str | None) -> str:
    """Never claim more precision than the query could support."""
    order = ["exact", "address", "locality"]
    if cap is None:
        return precision
    return order[max(order.index(precision), order.index(cap))]


def geocode_one(fetcher: Fetcher, name: str, address: str | None, region: str | None):
    """Nominatim free-text lookup, narrowing what we claim as we go.

    Named queries first. If those fail, the address alone, then progressively
    shorter tails of it. Anything found without the venue name cannot be the
    building and is never recorded as ``exact``: a barangay-level pin labelled
    approximate is useful, and one labelled exact is a lie.

    Returns ``(entry, reason)``; ``entry`` is None when nothing survives.
    """
    address = text_of(address)
    name = (name or "").strip()
    attempts = []
    if name and address:
        attempts.append((with_country(f"{name}, {address}"), True, None))
    if name:
        attempts.append((with_country(name), True, None))
    if address:
        attempts.append((with_country(address), False, "address"))
        attempts.extend(
            (with_country(tail), False, "locality") for tail in address_tails(address)
        )
    if not attempts:
        # Without either, the only query left to build was ", Philippines",
        # which asks for the country and gets it.
        return None, "no name or address to search"

    reason = "no result"
    for query, by_name, cap in attempts:
        results = fetcher.get_json(
            config.NOMINATIM_URL,
            {
                "q": query,
                "format": "jsonv2",
                "countrycodes": "ph",
                "limit": "5",
                # The address breakdown is what tells a town apart from a
                # barangay of the same name. See place_match.
                "addressdetails": "1",
            },
        )
        ranked: list[tuple[tuple[int, int, int], dict, float, float, int]] = []
        for order, hit in enumerate(results or []):
            here, rank = coords_of(hit), place_rank_of(hit)
            if here is None or rank is None or rank < _MIN_PLACE_RANK:
                continue
            lat, lon = here
            if not in_bounds(lat, lon):
                continue
            # Same rule as the OSM tier: the name and the region are separate
            # kinds of evidence, and one of them has to be convincing.
            named = by_name and score(name, hit.get("name") or "") >= _RATIO_ACCEPT
            # What, other than the name, explains this hit. For a query built
            # from the property name, that is where the rest of the name turns
            # up in the hit's address; for a query built from the address, it
            # is whether the hit repeats any of it.
            explained = place_match(name, hit) if by_name else 2 * int(supported(query, hit))
            if not named and not explained:
                # Nothing but "somewhere in the right quarter of the country",
                # which is how the Urdaneta Philippines Temple in Pangasinan
                # became WalterMart Balanga in Bataan, 140 km away.
                continue
            if not named and explained < 2 and not region_agrees(region, lat, lon):
                # Only a street or a barangay agrees, and those repeat across
                # towns, so the region has to agree as well. A town or province
                # match stands on its own: the region boxes are coarse enough
                # to put Bataan outside north-luzon, and they were losing the
                # correct Balanga hit for exactly that reason.
                continue
            # Rank rather than take the first. A region is a quarter of the
            # country, so "the first result that is in the right region" is
            # barely a choice at all, and it put two WalterMart branches on one
            # coordinate. Nominatim's own order breaks ties, and only ties.
            key = (int(named), explained, -order)
            ranked.append((key, hit, lat, lon, rank))
        ranked.sort(key=lambda item: item[0], reverse=True)
        for _, hit, lat, lon, rank in ranked:
            # A name can match a different building of the same name, so ask
            # what is at the coordinate before returning it. Rejecting here
            # rather than after the fact is what lets the ladder keep going:
            # "The Strip" matches a Quezon City node on both tiers, and only a
            # query built from its address reaches Capitol Commons in Pasig.
            if disagrees(fetcher, address, lat, lon):
                continue
            # place_rank rises with specificity: 30 is a building, 26 a street,
            # under 22 a town or larger. Say which one we got instead of
            # implying every pin is equally precise.
            precision = "exact" if rank >= 30 else "address" if rank >= 22 else "locality"
            precision = cap_precision(precision, cap)
            return {
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "source": "nominatim",
                "precision": precision,
                "matched": hit.get("display_name", "")[:120],
                "ref": f"{hit.get('osm_type', '?')}/{hit.get('osm_id', '?')}",
            }, ""
        if ranked:
            reason = "every candidate was somewhere the address does not mention"
        elif results:
            reason = "results outside region or bounds"
    return None, reason


# --------------------------------------------------------------------------
# refresh
# --------------------------------------------------------------------------


def refresh(malls: pd.DataFrame, cache_dir: Path) -> tuple[dict[str, dict], str]:
    """Resolve every property the registry cannot already place.

    Operator-supplied coordinates are never overwritten and never looked up, so
    a refresh costs one Overpass call plus one Nominatim call per genuinely
    unknown property.
    """
    entries = load()
    todo = [
        row for row in malls.to_dict("records")
        if not is_operator_placed(row)
        and key_of(row["chain"], row["mall_id"]) not in entries
    ]
    if not todo:
        return entries, "[geocode] registry already covers every property"

    lines = [f"[geocode] {len(todo)} propert{'y' if len(todo) == 1 else 'ies'} to resolve"]

    osm = Fetcher(
        cache_dir,
        rate=config.GEOCODE_RATE,
        timeout=config.GEOCODE_OVERPASS_TIMEOUT + 30,
        headers={"User-Agent": config.GEOCODER_USER_AGENT},
    )
    try:
        features = fetch_osm_features(osm)
        lines.append(f"[geocode] {len(features):,} OSM retail features in scope")
        unmatched = []
        proposed = []
        for row in todo:
            hit, reason = best_match(row["mall_name"], row.get("region"), features)
            if hit is None:
                unmatched.append((row, reason))
                continue
            proposed.append((row, {
                "lat": round(hit["lat"], 6),
                "lon": round(hit["lon"], 6),
                "source": "osm",
                "precision": "exact",
                "matched": hit["names"][0],
                "ref": hit["id"],
            }))
    finally:
        osm.close()

    nom = Fetcher(
        cache_dir,
        rate=config.GEOCODE_RATE,
        headers={"User-Agent": config.GEOCODER_USER_AGENT},
    )
    try:
        # Check the name match against the address before trusting it, and send
        # anything that fails down to the tier that reads addresses.
        for row, entry in proposed:
            complaint = address_disagrees(nom, row, entry)
            if complaint:
                lines.append(
                    f"[geocode]   rejected OSM {entry['ref']} for "
                    f"{key_of(row['chain'], row['mall_id'])}: {complaint}"
                )
                unmatched.append((row, f"OSM match rejected: {complaint}"))
                continue
            entries[key_of(row["chain"], row["mall_id"])] = entry
        lines.append(f"[geocode] OSM matched {len(todo) - len(unmatched)}, {len(unmatched)} left")

        failed = []
        for row, _ in unmatched:
            entry, reason = geocode_one(
                nom, row["mall_name"], text_of(row.get("address")), text_of(row.get("region"))
            )
            if entry is None:
                failed.append(f"{key_of(row['chain'], row['mall_id'])} ({reason})")
                continue
            # geocode_one already checked its own candidates against the
            # address, one rung at a time, so there is nothing left to re-ask.
            entries[key_of(row["chain"], row["mall_id"])] = entry
    finally:
        nom.close()
    lines.append(
        f"[geocode] Nominatim matched {len(unmatched) - len(failed)}, {len(failed)} unresolved"
    )
    for item in sorted(failed):
        lines.append(f"[geocode]   unresolved: {item}")

    save(entries)
    lines.extend(collisions(entries))
    lines.append(f"[geocode] registry now holds {len(entries):,} entries -> {REGISTRY}")
    return entries, "\n".join(lines)


def reverse_hit(fetcher: Fetcher, lat: float, lon: float) -> dict | None:
    """What OpenStreetMap says is at a coordinate, in the shape `supported` reads.

    None means nothing is there. Nominatim answers a reverse lookup in open
    water with an error rather than a place, which is the only cheap way to ask
    "is this pin even on land".
    """
    body = fetcher.get_json(
        config.NOMINATIM_REVERSE_URL,
        {"lat": f"{lat:.6f}", "lon": f"{lon:.6f}", "format": "jsonv2", "addressdetails": "1"},
    )
    if not isinstance(body, dict) or body.get("error"):
        return None
    address = body.get("address")
    if not isinstance(address, dict) or not address:
        # A response with no usable address breakdown says nothing about where
        # this is, and "says nothing" must not read as "is not on land".
        return None
    return {"name": body.get("name") or "", "address": address}


def disagrees(fetcher: Fetcher, address: str | None, lat: float, lon: float) -> str | None:
    """Why this coordinate cannot be this property, or None if nothing says so.

    The check only runs when the property came with an address, because an
    address is the one piece of evidence a name match did not already use: the
    OSM tier matches on name and region alone, and "The Strip" matched a node
    called "The Strip Mall" in Quezon City for a property whose own address
    says Capitol Commons, Pasig. Both names are the same and both places are in
    Metro Manila, so nothing in the matcher could tell them apart. Asking what
    is at the coordinate can.

    Only the address speaks here, never the property name. Reading the name in
    as well is how a reverse result of {"village": "Ayala", "city": "Makati"}
    would corroborate Ayala Malls Serin in Tagaytay: the brand is in the name,
    the brand turns up in half the villages in the country, and neither
    Tagaytay nor Cavite was ever checked.

    Without an address there is nothing to check against, and an uncorroborated
    pin still beats no pin at all, so those are kept.
    """
    if not address:
        return None
    here = reverse_hit(fetcher, lat, lon)
    if here is None:
        return "nothing is at that coordinate"
    if supported(address, here, place_only=True):
        return None
    where = ", ".join(str(here["address"].get(k)) for k in _SETTLEMENT_KEYS if here["address"].get(k))
    return f"reverse lookup says {where or 'nowhere named'}, which the address does not mention"


def address_disagrees(fetcher: Fetcher, row: dict, entry: dict) -> str | None:
    """`disagrees` for a mall row and a registry entry."""
    return disagrees(fetcher, text_of(row.get("address")), entry["lat"], entry["lon"])


def verify_placements(fetcher: Fetcher, malls: pd.DataFrame) -> tuple[list[str], int]:
    """Ask what is actually at every pin, and report the ones nothing explains.

    Choosing a coordinate and checking one are different questions, and the
    checking one is the only one that catches a coordinate we never chose. The
    operator tier is unchecked by construction - it arrives with the scrape and
    the matcher never sees it - so a longitude Ayala got wrong reached the map
    with the highest trust label in the system and stayed there until someone
    noticed a mall drawn in the sea.

    Two verdicts. `unplaced` means the reverse lookup found nothing at all,
    which for a shopping mall means water or wilderness; it is never a false
    alarm. `unexplained` means something is there but its address repeats
    nothing from the property's own name or address; it is a prompt to look,
    and it does misfire on properties whose only name is a barangay the reverse
    lookup did not happen to mention.
    """
    placed = malls[malls["lat"].notna()]
    hard: list[str] = []
    soft: list[str] = []
    for row in placed.to_dict("records"):
        key = key_of(row["chain"], row["mall_id"])
        lat, lon = float(row["lat"]), float(row["lon"])
        here = reverse_hit(fetcher, lat, lon)
        label = f"{key} ({row['geo_source']}/{row['geo_precision']}) at {lat:.5f},{lon:.5f}"
        if here is None:
            hard.append(f"[geocode]   unplaced: {label} - nothing is at this coordinate")
            continue
        address = text_of(row.get("address"))
        if address is None:
            # Nothing to check the pin against. Most WalterMart branches arrive
            # with no address at all, and flagging every one of them as
            # unexplained would bury the pins that are genuinely wrong.
            continue
        if not supported(address, here, place_only=True):
            where = ", ".join(
                str(here["address"].get(k)) for k in _SETTLEMENT_KEYS if here["address"].get(k)
            )
            soft.append(f"[geocode]   unexplained: {label} - reverse lookup says {where or 'nowhere named'}")
    lines = [f"[geocode] verified {len(placed)} placed properties"]
    lines += hard
    if soft:
        lines.append(f"[geocode] {len(soft)} pins whose address explains nothing about the property:")
        lines += soft
    if not hard and not soft:
        lines.append("[geocode] every pin is on land and consistent with its address")
    return lines, len(hard)


def collisions(entries: dict[str, dict]) -> list[str]:
    """Report properties that resolved to the same building.

    A town centre is shared by design - that is what `locality` precision
    means - but two properties claiming one building means at least one of them
    is wrong, and it is invisible in the data: both rows look complete. On the
    map it appears as a cluster of two, which is what a cluster of two is
    supposed to look like. Naming it here is the only place it shows up.
    """
    claims: dict[tuple[str, str], list[str]] = {}
    for key, entry in entries.items():
        if entry.get("precision") == "locality" or not entry.get("ref"):
            continue
        claims.setdefault((entry["source"], entry["ref"]), []).append(key)
    lines = []
    for (source, ref), keys in sorted(claims.items()):
        if len(keys) > 1:
            lines.append(
                f"[geocode]   collision: {', '.join(sorted(keys))} all resolved to "
                f"{source} {ref}; at most one of them can be right"
            )
    return lines
