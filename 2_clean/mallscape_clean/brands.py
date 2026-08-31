"""Resolve brand keys to a canonical brand.

`brand_key` normalizes a store name; it does not decide that two names are the
same business. Without that second step `starbucks` and `starbucks coffee` are
two brands with 57 and 79 malls, and neither number is Starbucks' reach.

Merging is deliberately **explicit**. The alias table is an allow-list read
from `registry/brand_aliases.json`; nothing merges unless it is written there.
Similarity never acts on the data, because similarity cannot tell these apart:

    mi store (14 malls)   vs  sm store (69 malls)     Xiaomi vs The SM Store
    bpi (61)              vs  bpi atm (21)            a branch is not an ATM

The first is a false positive an automatic merger would have taken; the second
is a distinction an earlier version of this project destroyed and had to undo.
An allow-list cannot make either mistake.
"""

from __future__ import annotations

import json
from importlib import resources

import pandas as pd


def load_aliases() -> dict[str, str]:
    """`{variant: canonical}`, read from the committed registry."""
    try:
        raw = resources.files("mallscape_scrape.registry").joinpath("brand_aliases.json").read_text()
    except FileNotFoundError:
        return {}
    doc = json.loads(raw)
    aliases: dict[str, str] = {}
    for canonical, variants in doc.get("aliases", {}).items():
        for variant in variants:
            if variant == canonical:
                continue
            aliases[variant] = canonical
    return aliases


def resolve(brand_keys: pd.Series) -> pd.Series:
    """Map each key to its canonical form, leaving unlisted keys untouched."""
    aliases = load_aliases()
    if not aliases:
        return brand_keys.copy()
    # One hop only. A chain of aliases would make the result depend on
    # iteration order, so the registry is required to point straight at the
    # canonical name.
    return brand_keys.map(lambda k: aliases.get(k, k))
