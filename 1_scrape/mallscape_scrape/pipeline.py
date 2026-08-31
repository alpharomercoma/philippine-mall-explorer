"""Stage 1 entry point: scrape chains and write this stage's artifacts.

Owns everything about producing a snapshot's `1_scrape/` directory, including
the carry-forward rule that keeps a single-chain run from silently dropping
the other chains.
"""

from __future__ import annotations

import os

import pandas as pd

from mallscape_core import config, storage
from mallscape_core.geo import region_for
from mallscape_scrape import geocode, validate
from mallscape_scrape.fetch import Fetcher
from mallscape_scrape.registry_of_scrapers import SCRAPERS


def run(chains: list[str], run_date: str, rate: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_malls, all_stores, warnings = [], [], []
    confirmed_empty: set[tuple[str, str]] = set()

    # Seed from this date's snapshot if it exists, else carry the previous run
    # forward, so scraping one chain never drops the rest.
    prev_malls = storage.read(run_date, storage.SCRAPE, "malls")
    prev_stores = storage.read(run_date, storage.SCRAPE, "stores")
    partial = len(chains) < len(SCRAPERS)
    if prev_malls is None and partial:
        carry_from = storage.previous_run(run_date)
        if carry_from:
            prev_malls = storage.read(carry_from, storage.SCRAPE, "malls")
            prev_stores = storage.read(carry_from, storage.SCRAPE, "stores")
            if prev_malls is not None:
                kept = sorted(set(prev_malls["chain"]) - set(chains))
                print(f"[scrape] carrying forward {carry_from} for chains: {kept}")

    for name in chains:
        cls = SCRAPERS[name]
        fetcher = Fetcher(storage.cache_dir(run_date, name), rate=rate, headers=cls.extra_headers)
        scraper = cls(fetcher)
        try:
            malls, stores = scraper.scrape_all()
        finally:
            fetcher.close()
        print(
            f"[{name}] done: {len(malls)} malls, {len(stores)} stores "
            f"({fetcher.requests_made} requests, {fetcher.cache_hits} cache hits)"
        )
        all_malls.extend(m.to_row() for m in malls)
        all_stores.extend(s.to_row() for s in stores)
        warnings.extend(scraper.warnings)
        confirmed_empty.update((name, mall_id) for mall_id in scraper.confirmed_empty)

    # Only three operators publish a region. Fill the rest from name and
    # address so region filtering reaches every property, and report whatever
    # still cannot be resolved rather than leaving it silently null.
    unresolved = []
    for row in all_malls:
        if not row.get("region"):
            row["region"] = region_for(row.get("mall_name"), row.get("address"))
            if not row["region"]:
                unresolved.append(row["mall_id"])
    if unresolved:
        print(f"[scrape] region unresolved for {len(unresolved)} malls: {sorted(unresolved)[:8]}")

    malls_df = pd.DataFrame(all_malls)
    stores_df = pd.DataFrame(all_stores)
    # Stamp only what was fetched now; carried rows keep their true date so a
    # stale chain is never presented as fresh.
    malls_df["scraped_at"] = run_date
    stores_df["scraped_at"] = run_date
    if prev_malls is not None and partial:
        # ignore_index because both sides count from zero: without it the joined
        # frame has each low label twice, and any later `.at[label] = ...` write
        # hits both rows. That is how four Pasay properties ended up on Ortigas
        # coordinates, drawn on the map as confidently as the correct ones.
        malls_df = pd.concat(
            [prev_malls[~prev_malls["chain"].isin(chains)], malls_df], ignore_index=True
        )
        stores_df = pd.concat(
            [prev_stores[~prev_stores["chain"].isin(chains)], stores_df], ignore_index=True
        )

    malls_df = place(malls_df)

    guard_against_collapse(run_date, stores_df)
    storage.validate_snapshot_frames(malls_df, stores_df)
    storage.write(run_date, storage.SCRAPE, "malls", malls_df)
    storage.write(run_date, storage.SCRAPE, "stores", stores_df)
    report = validate.build_report(run_date, malls_df, stores_df, warnings, confirmed_empty)
    storage.write_text(run_date, storage.SCRAPE, "run_report.md", report)
    print("\n" + report)
    return malls_df, stores_df


def guard_against_collapse(run_date: str, stores_df: pd.DataFrame) -> None:
    """Refuse to write a snapshot in which a chain lost most of its listings.

    A directory that served hundreds of tenants last month and near zero today
    is almost always the operator's site breaking, not the malls emptying;
    Araneta's directory served empty gallery markup for a period in 2026-08
    while its per-tenant records were still live. An unattended monthly run
    must stop on that rather than publish it. When the shrink is real, set
    MALLSCAPE_ACCEPT_COLLAPSE to the chain names (comma separated, or "all")
    for that one run.
    """
    previous = storage.previous_run(run_date)
    if previous is None:
        return
    prev_stores = storage.read(previous, storage.SCRAPE, "stores")
    if prev_stores is None:
        return
    accepted = {
        c.strip() for c in os.environ.get("MALLSCAPE_ACCEPT_COLLAPSE", "").split(",") if c.strip()
    }
    before = prev_stores.groupby("chain").size()
    after = stores_df.groupby("chain").size()
    def collapsed_for(chain) -> bool:
        now = after.get(chain, 0)
        halved = before[chain] >= 50 and now < before[chain] * 0.5
        vanished = before[chain] >= 20 and now == 0
        return (halved or vanished) and chain not in accepted and "all" not in accepted

    collapsed = [
        f"{chain}: {int(before[chain]):,} -> {int(after.get(chain, 0)):,}"
        for chain in before.index
        if collapsed_for(chain)
    ]
    if collapsed:
        raise SystemExit(
            "refusing to write the snapshot: these chains lost more than half "
            f"their listings since {previous}, which usually means the source "
            f"broke, not the malls: {'; '.join(collapsed)}. If the shrink is "
            "real, rerun with MALLSCAPE_ACCEPT_COLLAPSE=<chains|all>."
        )


def place(malls_df: pd.DataFrame) -> pd.DataFrame:
    """Attach committed coordinates, then use them to settle any open region.

    Reads the registry only, so this is offline and deterministic. Properties
    the registry cannot place are named on stdout rather than quietly dropped
    from the map; `mallscape geocode` is what resolves them.
    """
    malls_df, unplaced = geocode.attach(malls_df)
    # A coordinate answers the region question outright, so anything the text
    # rules could not classify gets a second chance here rather than staying null.
    for i, row in malls_df.iterrows():
        if not row.get("region") and pd.notna(row["lat"]):
            malls_df.at[i, "region"] = region_for(lat=row["lat"], lon=row["lon"])
    placed = int(malls_df["lat"].notna().sum())
    print(f"[scrape] coordinates: {placed}/{len(malls_df)} properties placed")
    if unplaced:
        print(
            f"[scrape] {len(unplaced)} without coordinates, run `mallscape geocode`: "
            f"{sorted(unplaced)[:8]}"
        )
    return malls_df


def geocode_run(run_date: str, offline: bool = False, verify: bool = False) -> pd.DataFrame:
    """Stage 1b. Resolve missing coordinates over the network and re-place the
    snapshot, without re-scraping any directory.

    `offline` skips the lookup and replays the committed registry alone, which
    is what repairs a snapshot whose coordinates were written to the wrong rows.
    `verify` adds a reverse lookup per placed property afterwards, which is the
    only check that reads the operator tier as well as the resolved one.
    """
    malls_df = storage.read(run_date, storage.SCRAPE, "malls")
    if malls_df is None:
        raise SystemExit(f"no stage 1 malls table for {run_date}; run `mallscape scrape` first")
    if offline:
        print("[geocode] offline: re-applying the committed registry, no lookups")
    else:
        _, log = geocode.refresh(malls_df, storage.cache_dir(run_date, "geocode"))
        print(log)
    malls_df = place(malls_df)
    storage.write(run_date, storage.SCRAPE, "malls", malls_df)
    if verify:
        fetcher = Fetcher(
            storage.cache_dir(run_date, "geocode"),
            rate=config.GEOCODE_RATE,
            headers={"User-Agent": config.GEOCODER_USER_AGENT},
        )
        try:
            # Bypass the cache: a stored answer would only tell us where the
            # pin was the last time we asked, and the pin is what changed.
            with fetcher.bypass_cache():
                lines, bad = geocode.verify_placements(fetcher, malls_df)
        finally:
            fetcher.close()
        print("\n".join(lines))
        if bad:
            raise SystemExit(f"{bad} pin(s) are not on land; fix them before publishing")
    return malls_df
