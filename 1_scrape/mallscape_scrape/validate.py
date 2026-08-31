"""Per-run validation report: catches site redesigns and partial scrapes by
comparing the fresh snapshot against the previous one."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import pandas as pd

from mallscape_core import storage

# Properties known to publish no tenant directory, each with the evidence and
# the date it was last confirmed against the operator's own site.
EMPTY_DIRECTORIES = Path(__file__).parent / "registry" / "empty_directories.json"

DROP_ALERT = 0.20  # alert when a mall loses more than 20% of its stores

# A mall under this fraction of its chain's median is reported as thin. It is a
# prompt to look, not a verdict: chains genuinely run small provincial branches
# next to their flagships. The point is that nobody has to notice the outlier
# by eye.
THIN_FRACTION = 0.25


def known_empty() -> dict[str, dict]:
    """The accounted-for empties, keyed ``chain:mall_id``."""
    if not EMPTY_DIRECTORIES.exists():
        # A missing registry must not quietly reclassify every accounted-for
        # empty directory as an unexplained defect.
        raise SystemExit(f"registry file missing: {EMPTY_DIRECTORIES}")
    return json.loads(EMPTY_DIRECTORIES.read_text())["entries"]


def with_property_type(malls: pd.DataFrame) -> pd.DataFrame:
    """The frame with a property_type on every row.

    A property with no type recorded is a mall: that is what the column means
    when a chain publishes only malls, and it is the reading that puts an
    unclassified empty property in the section that gets read rather than the
    one that gets excused.
    """
    malls = malls.copy()
    if "property_type" not in malls.columns:
        malls["property_type"] = "mall"
    malls["property_type"] = malls["property_type"].fillna("mall").replace("", "mall")
    return malls


def empty_section(
    malls: pd.DataFrame,
    stores: pd.DataFrame,
    confirmed_empty: set[tuple[str, str]],
) -> list[str]:
    """Every property that published no tenants, split by whether that is a defect.

    A mall with no tenants is a hole in the data: either the operator's
    directory broke, or ours did. An amusement park or an office annex with
    none is just what that property is. Reporting them in one undifferentiated
    list, which is what this used to do, buries the first kind under the
    second.
    """
    counts = stores.groupby(["chain", "mall_id"]).size() if len(stores) else {}
    malls = with_property_type(malls)
    lines: list[str] = []
    rows = []
    for row in malls.itertuples():
        if counts.get((row.chain, row.mall_id), 0):
            continue
        rows.append((row.property_type, row.chain, row.mall_id, row.mall_name))
    if not rows:
        return ["", "## Properties with no tenants", "",
                "- none: every property published at least one tenant", ""]
    accounted = known_empty()
    lines += ["", "## Properties with no tenants", ""]
    malls_empty = sorted(r for r in rows if r[0] == "mall")
    other_empty = sorted(r for r in rows if r[0] != "mall")
    unexplained = [r for r in malls_empty if f"{r[1]}:{r[2]}" not in accounted]
    explained = [r for r in malls_empty if f"{r[1]}:{r[2]}" in accounted]
    if unexplained:
        # The whole point of the split. A mall nobody has accounted for is a
        # defect in this pipeline until someone proves otherwise, and it says
        # so rather than joining a list that is mostly known gaps.
        lines.append(
            f"- ⚠ {len(unexplained)} MALL(S) PUBLISHED NOTHING AND ARE NOT ACCOUNTED FOR. "
            f"Investigate each one, then either fix the scraper or record the evidence "
            f"in {EMPTY_DIRECTORIES.name}:"
        )
        for _, chain, mall_id, name in unexplained:
            confirmed = (
                "confirmed empty against the live site"
                if (chain, mall_id) in confirmed_empty
                else "NOT re-checked, so this may be a failed request rather than an empty mall"
            )
            lines.append(f"  - {chain}:{mall_id} ({name}) - {confirmed}")
    if explained:
        lines.append(f"- {len(explained)} mall(s) publish no directory, each on the record:")
        for _, chain, mall_id, name in explained:
            entry = accounted[f"{chain}:{mall_id}"]
            lines.append(f"  - {chain}:{mall_id} ({name}) - checked {entry['checked']}: {entry['evidence']}")
    if other_empty:
        listed = ", ".join(f"{c}:{m}" for _, c, m, _ in other_empty)
        kinds = sorted({r[0] for r in other_empty})
        lines.append(
            f"- {len(other_empty)} non-mall propert(ies) published nothing "
            f"({', '.join(kinds)}), which is expected: {listed}"
        )
    stale = sorted(set(accounted) - {f"{r[1]}:{r[2]}" for r in rows})
    if stale:
        # An entry that stops applying has to go, or the file slowly becomes a
        # licence for defects. SM City La Union was on this list until it
        # served 199 tenants.
        lines.append(
            f"- {len(stale)} entr(ies) in {EMPTY_DIRECTORIES.name} no longer apply and "
            f"should be deleted: {', '.join(stale)}"
        )
    return lines


def thin_section(malls: pd.DataFrame, stores: pd.DataFrame) -> list[str]:
    """Malls carrying far fewer tenants than the rest of their own chain.

    Compared within the chain rather than across all of them, because the
    chains differ by an order of magnitude in how much they publish: a
    WalterMart branch at 30 tenants is normal and an SM mall at 30 is not.
    """
    counts = stores.groupby(["chain", "mall_id"]).size() if len(stores) else {}
    malls = with_property_type(malls)
    lines: list[str] = []
    for chain, chain_malls in malls.groupby("chain"):
        real = chain_malls[chain_malls["property_type"] == "mall"]
        sizes = {r.mall_id: int(counts.get((chain, r.mall_id), 0)) for r in real.itertuples()}
        nonzero = sorted(v for v in sizes.values() if v)
        if len(nonzero) < 4:  # too few malls for "typical" to mean anything
            continue
        median = statistics.median(nonzero)
        floor = median * THIN_FRACTION
        thin = sorted((v, k) for k, v in sizes.items() if 0 < v < floor)
        for size, mall_id in thin:
            lines.append(
                f"  - {chain}:{mall_id}: {size} tenants against a chain median of {median:g}"
            )
    if not lines:
        return ["", "## Suspiciously thin malls", "", "- none: every mall is within range of its chain's median"]
    return [
        "",
        "## Suspiciously thin malls",
        "",
        f"- ⚠ {len(lines)} malls hold under {THIN_FRACTION:.0%} of their chain's median tenant count:",
        *lines,
    ]


def build_report(
    run_date: str,
    malls: pd.DataFrame,
    stores: pd.DataFrame,
    warnings: list[str],
    confirmed_empty: set[tuple[str, str]] | None = None,
) -> str:
    lines = [f"# mallscape run report - {run_date}", ""]

    for chain, chain_malls in malls.groupby("chain"):
        chain_stores = stores[stores["chain"] == chain]
        lines.append(
            f"- **{chain}**: {len(chain_malls)} malls, {len(chain_stores)} store rows"
        )
    lines += empty_section(malls, stores, confirmed_empty or set())
    lines += thin_section(malls, stores)

    prev_date = storage.previous_run(run_date)
    if prev_date:
        lines.append(f"\n## Diff vs {prev_date}")
        prev_stores = storage.read(prev_date, storage.SCRAPE, "stores")
        prev_malls = storage.read(prev_date, storage.SCRAPE, "malls")
        if prev_malls is not None:
            gone = set(prev_malls["mall_id"]) - set(malls["mall_id"])
            new = set(malls["mall_id"]) - set(prev_malls["mall_id"])
            if gone:
                lines.append(f"- ⚠ malls disappeared: {sorted(gone)}")
            if new:
                lines.append(f"- malls added: {sorted(new)}")
        if prev_stores is not None:
            cur = stores.groupby(["chain", "mall_id"]).size()
            prev = prev_stores.groupby(["chain", "mall_id"]).size()
            both = cur.index.intersection(prev.index)
            delta = (cur[both] - prev[both]) / prev[both]
            drops = delta[delta < -DROP_ALERT]
            if not drops.empty:
                lines.append(f"- ⚠ store-count drops >{DROP_ALERT:.0%} (possible redesign):")
                for mall_key, pct in drops.items():
                    lines.append(f"  - {mall_key}: {prev[mall_key]} → {cur[mall_key]} ({pct:+.0%})")
            else:
                lines.append("- no anomalous store-count drops")
    else:
        lines.append("\n_First run - no previous snapshot to diff against._")

    if warnings:
        lines.append("\n## Scraper warnings")
        lines.extend(f"- {w}" for w in warnings)

    report = "\n".join(lines) + "\n"
    return report
