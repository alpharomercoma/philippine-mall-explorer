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


def empty_properties(malls: pd.DataFrame, stores: pd.DataFrame) -> list[tuple[str, str, str, str]]:
    """(property_type, chain, mall_id, mall_name) for every property with no tenants."""
    counts = stores.groupby(["chain", "mall_id"]).size() if len(stores) else {}
    return [
        (row.property_type, row.chain, row.mall_id, row.mall_name)
        for row in with_property_type(malls).itertuples()
        if not counts.get((row.chain, row.mall_id), 0)
    ]


def unexplained_empty(
    rows: list[tuple[str, str, str, str]], accounted: dict[str, dict]
) -> list[tuple[str, str, str, str]]:
    """The empty malls nobody has accounted for: a defect until proven otherwise."""
    return sorted(r for r in rows if r[0] == "mall" and f"{r[1]}:{r[2]}" not in accounted)


def diff_previous(
    run_date: str, malls: pd.DataFrame, stores: pd.DataFrame
) -> tuple[str | None, set[str], set[str], list[tuple[tuple[str, str], int, int, float]]]:
    """Against the snapshot before this one: (its date, malls gone, malls new,
    per-mall store-count drops beyond DROP_ALERT as (key, before, after, change))."""
    prev_date = storage.previous_run(run_date)
    gone: set[str] = set()
    new: set[str] = set()
    drops: list[tuple[tuple[str, str], int, int, float]] = []
    if not prev_date:
        return None, gone, new, drops
    prev_malls = storage.read(prev_date, storage.SCRAPE, "malls")
    prev_stores = storage.read(prev_date, storage.SCRAPE, "stores")
    if prev_malls is not None:
        gone = set(prev_malls["mall_id"]) - set(malls["mall_id"])
        new = set(malls["mall_id"]) - set(prev_malls["mall_id"])
    if prev_stores is not None:
        cur = stores.groupby(["chain", "mall_id"]).size()
        prev = prev_stores.groupby(["chain", "mall_id"]).size()
        both = cur.index.intersection(prev.index)
        delta = (cur[both] - prev[both]) / prev[both]
        drops = [
            (key, int(prev[key]), int(cur[key]), float(pct))
            for key, pct in delta[delta < -DROP_ALERT].items()
        ]
    return prev_date, gone, new, drops


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
    rows = empty_properties(malls, stores)
    if not rows:
        return ["", "## Properties with no tenants", "",
                "- none: every property published at least one tenant", ""]
    accounted = known_empty()
    lines: list[str] = ["", "## Properties with no tenants", ""]
    malls_empty = sorted(r for r in rows if r[0] == "mall")
    other_empty = sorted(r for r in rows if r[0] != "mall")
    unexplained = unexplained_empty(rows, accounted)
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

    prev_date, gone, new, drops = diff_previous(run_date, malls, stores)
    if prev_date:
        lines.append(f"\n## Diff vs {prev_date}")
        if gone:
            lines.append(f"- ⚠ malls disappeared: {sorted(gone)}")
        if new:
            lines.append(f"- malls added: {sorted(new)}")
        if storage.read(prev_date, storage.SCRAPE, "stores") is not None:
            if drops:
                lines.append(f"- ⚠ store-count drops >{DROP_ALERT:.0%} (possible redesign):")
                for mall_key, before, after, pct in drops:
                    lines.append(f"  - {mall_key}: {before} → {after} ({pct:+.0%})")
            else:
                lines.append("- no anomalous store-count drops")
    else:
        lines.append("\n_First run - no previous snapshot to diff against._")

    if warnings:
        lines.append("\n## Scraper warnings")
        lines.extend(f"- {w}" for w in warnings)

    report = "\n".join(lines) + "\n"
    return report


def health(
    run_date: str,
    malls: pd.DataFrame,
    stores: pd.DataFrame,
    *,
    chains: list[str],
    failed_chains: dict[str, str],
    carried: set[str],
    failed_malls: dict[str, dict[str, str]],
    alerts: dict[str, list[str]],
) -> dict:
    """What the weekly check fails on, kept apart from the report's prose.

    `problems` are the defects someone has to act on: a chain that raised, a
    chain carried forward because its listings collapsed, a mall whose scrape
    raised, a scraper alert (the operator's site drifted), and a mall with no
    tenants that nobody has accounted for. Every one of them still lets a
    monthly run publish, which is why they need a check that fails instead.

    `notices` are worth reading but are not defects: a mall delisted or a
    directory shrinking is usually the operator's real portfolio, and it would
    stay "failed" every week until the next snapshot moved the baseline.
    """
    problems = [f"{chain}: scrape failed entirely ({reason})" for chain, reason in sorted(failed_chains.items())]
    problems += [
        f"{chain}: listings collapsed against the previous snapshot; its rows were carried forward"
        for chain in sorted(carried - set(failed_chains))
    ]
    for chain in sorted(failed_malls):
        problems += [f"{chain}: {msg}" for msg in failed_malls[chain].values()]
    for chain in sorted(alerts):
        problems += [f"{chain}: {msg}" for msg in alerts[chain]]
    # A mall whose scrape raised is already named above; it is empty because
    # it failed, not because the operator published nothing.
    raised = {(chain, mall_id) for chain, malls_failed in failed_malls.items() for mall_id in malls_failed}
    problems += [
        f"{chain}:{mall_id} ({name}) published no tenants and is not in {EMPTY_DIRECTORIES.name}"
        for _, chain, mall_id, name in unexplained_empty(empty_properties(malls, stores), known_empty())
        if (chain, mall_id) not in raised
    ]
    prev_date, gone, _, drops = diff_previous(run_date, malls, stores)
    # A one-chain run carries the rest forward unscraped; their failures, if
    # any, belong to whichever run fetched them, and this one cannot vouch.
    unchecked = sorted(set(malls["chain"]) - set(chains))
    notices = [f"not scraped in this run, so not checked: {unchecked}"] if unchecked else []
    notices += [f"malls no longer listed since {prev_date}: {sorted(gone)}"] if gone else []
    notices += [
        f"{chain}:{mall_id}: {before} → {after} tenants since {prev_date} ({pct:+.0%})"
        for (chain, mall_id), before, after, pct in drops
    ]
    return {"run_date": run_date, "chains": sorted(chains), "problems": problems, "notices": notices}
