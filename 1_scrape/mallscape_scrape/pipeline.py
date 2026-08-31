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

    succeeded = 0
    for name in chains:
        cls = SCRAPERS[name]
        fetcher = Fetcher(storage.cache_dir(run_date, name), rate=rate, headers=cls.extra_headers)
        scraper = cls(fetcher)
        try:
            malls, stores = scraper.scrape_all()
        except Exception as exc:
            # One operator refusing this runner's IP outright (SM's WAF blocks
            # cloud address ranges wholesale) must not cost the other nine
            # their month. The chain contributes nothing here, which the
            # collapse reconciliation below turns into last month's rows.
            warnings.append(
                f"[{name}] scrape failed entirely ({type(exc).__name__}: {exc}); "
                "expecting the previous snapshot's rows to be carried forward"
            )
            print(f"[{name}] FAILED: {type(exc).__name__}: {exc}")
            continue
        finally:
            fetcher.close()
        succeeded += 1
        print(
            f"[{name}] done: {len(malls)} malls, {len(stores)} stores "
            f"({fetcher.requests_made} requests, {fetcher.cache_hits} cache hits)"
        )
        all_malls.extend(m.to_row() for m in malls)
        all_stores.extend(s.to_row() for s in stores)
        warnings.extend(scraper.warnings)
        confirmed_empty.update((name, mall_id) for mall_id in scraper.confirmed_empty)
    if not succeeded:
        raise SystemExit(
            "every chain failed to scrape; that is this runner's network, not "
            "ten simultaneous site redesigns. Nothing written."
        )

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

    malls_df, stores_df, carried = reconcile_collapse(run_date, malls_df, stores_df)
    if carried:
        confirmed_empty = {(c, m) for c, m in confirmed_empty if c not in carried}
        warnings.extend(
            f"[{chain}] listings collapsed against the previous snapshot; carried "
            f"that snapshot's rows forward instead (their `fetched` date says so)"
            for chain in sorted(carried)
        )

    malls_df = place(malls_df)

    storage.validate_snapshot_frames(malls_df, stores_df)
    storage.write(run_date, storage.SCRAPE, "malls", malls_df)
    storage.write(run_date, storage.SCRAPE, "stores", stores_df)
    report = validate.build_report(run_date, malls_df, stores_df, warnings, confirmed_empty)
    storage.write_text(run_date, storage.SCRAPE, "run_report.md", report)
    print("\n" + report)
    return malls_df, stores_df


def reconcile_collapse(
    run_date: str, malls_df: pd.DataFrame, stores_df: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, set[str]]:
    """Keep last month's rows for any chain whose listings collapsed.

    A directory that served hundreds of tenants last month and near zero today
    is almost always the operator's site breaking, not the malls emptying;
    Araneta's directory served empty gallery markup through 2026-08 while its
    per-tenant records were still live. For an unattended monthly run the
    least-wrong answer is the previous snapshot's rows for that chain alone:
    stale beats gone, the chain's `fetched` date in the report says exactly
    how stale, and every other chain stays fresh. When the shrink is real,
    set MALLSCAPE_ACCEPT_COLLAPSE to the chain names (comma separated, or
    "all") for that one run and the new rows are kept as scraped.

    Returns the possibly spliced frames and the chains carried forward.
    """
    previous = storage.previous_run(run_date)
    prev_stores = storage.read(previous, storage.SCRAPE, "stores") if previous else None
    prev_malls = storage.read(previous, storage.SCRAPE, "malls") if previous else None
    if prev_stores is None or prev_malls is None:
        return malls_df, stores_df, set()
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

    carried = {chain for chain in before.index if collapsed_for(chain)}
    if not carried:
        return malls_df, stores_df, set()
    for chain in sorted(carried):
        print(
            f"[scrape] {chain}: {int(before[chain]):,} -> {int(after.get(chain, 0)):,} "
            f"listings since {previous}; the source likely broke, keeping the "
            f"{previous} rows (MALLSCAPE_ACCEPT_COLLAPSE={chain} accepts the shrink)"
        )
    malls_df = pd.concat(
        [malls_df[~malls_df["chain"].isin(carried)], prev_malls[prev_malls["chain"].isin(carried)]],
        ignore_index=True,
    )
    stores_df = pd.concat(
        [stores_df[~stores_df["chain"].isin(carried)], prev_stores[prev_stores["chain"].isin(carried)]],
        ignore_index=True,
    )
    return malls_df, stores_df, carried


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
