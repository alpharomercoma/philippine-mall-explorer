"""Integration: stages hand off to each other correctly.

Unit tests cover one function against fixed input. These cover the contract
between stages, which is where the expensive bugs have historically been:
a stage writing where the next one does not read, or a schema drifting.
Everything runs against a temporary data directory, so no network and no
dependency on the committed snapshot.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

import pandas as pd
import pytest

from mallscape_core import storage

MALLS = pd.DataFrame({
    "chain": ["sm", "sm", "ayala"],
    "mall_id": ["sm-a", "sm-b", "ay-a"],
    "mall_name": ["SM A", "SM B", "Ayala A"],
    "region": ["metro-manila", "visayas", "visayas"],
    "address": [None, None, None],
    "mall_code": ["A", "B", "1"],
    "source_url": ["u", "u", "u"],
    "property_type": ["mall", "residential-retail", "mall"],
    # one placed by the operator, one by the registry, one unplaceable
    "lat": [14.55, 10.31, None],
    "lon": [121.02, 123.90, None],
    "geo_source": ["operator", "osm", None],
    "geo_precision": ["exact", "exact", None],
    "scraped_at": ["2026-01-01"] * 3,
})

STORES = pd.DataFrame({
    "chain": ["sm", "sm", "sm", "ayala"],
    "mall_id": ["sm-a", "sm-a", "sm-b", "ay-a"],
    "store_name_raw": ["JOLLIBEE", "WATSONS", "JOLLIBEE", "JOLLIBEE"],
    "category": ["dining", "wellness", "dining", "dine"],
    "floor": ["2ND FLOOR", "GF", "2F", None],
    "building": [None, None, None, None],
    "phone": ["0917-123-4567", None, None, None],
    "source": ["sm-api"] * 3 + ["ayala-api"],
    "scraped_at": ["2026-01-01"] * 4,
})


@pytest.fixture
def snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    storage.write("2026-01-01", storage.SCRAPE, "malls", MALLS)
    storage.write("2026-01-01", storage.SCRAPE, "stores", STORES)
    return "2026-01-01"


def test_clean_reads_stage1_and_writes_stage2(snapshot):
    from mallscape_clean import pipeline as clean_stage

    clean_stage.run(snapshot)
    out = storage.read(snapshot, storage.CLEAN, "stores_clean")
    assert out is not None and len(out) == len(STORES)
    # stage 1 must be untouched by stage 2
    assert storage.read(snapshot, storage.SCRAPE, "stores").equals(STORES)
    # the harmonized category collapses "dining" and "dine"
    assert set(out[out.store_name == "Jollibee"].category_std) == {"dining"}


def test_report_prefers_clean_output(snapshot):
    from mallscape_clean import pipeline as clean_stage
    from mallscape_report import pipeline as report_stage

    clean_stage.run(snapshot)
    report_stage.run(snapshot, quiet=True)
    summary = storage.read(snapshot, storage.REPORT, "brand_summary")
    assert summary is not None
    jollibee = summary[summary.brand_key == "jollibee"].iloc[0]
    assert jollibee.n_malls_total == 3      # present in all three properties
    assert bool(jollibee.in_multiple_chains) is True


def test_website_bundle_matches_snapshot_totals(snapshot):
    from mallscape_clean import pipeline as clean_stage
    from mallscape_website import bundle

    clean_stage.run(snapshot)
    _, data = bundle.build(snapshot)
    assert data["totals"]["properties"] == len(MALLS)
    assert data["totals"]["listings"] == len(STORES)
    assert data["totals"]["malls"] == 2      # one is residential-retail
    assert len(data["malls"]) == len(MALLS)
    assert data["schema"] == 4
    assert "quality" in data
    assert data["brandCategories"]


def test_website_bundle_carries_usable_coordinates(snapshot):
    """The map can only be as good as what reaches the bundle, so the contract
    is checked here rather than in the browser: every plotted property has a
    coordinate inside the country, and an unplaced one is null, not zero."""
    from mallscape_clean import pipeline as clean_stage
    from mallscape_core.geo import in_bounds
    from mallscape_website import bundle

    clean_stage.run(snapshot)
    _, data = bundle.build(snapshot)
    lat_min, lat_max, lon_min, lon_max = 4.5, 21.5, 116.0, 127.0
    placed = [row for row in data["malls"] if row[5] is not None]
    assert data["totals"]["mapped"] == len(placed) == 2
    for row in placed:
        assert in_bounds(row[5], row[6]), row
        assert lat_min <= row[5] <= lat_max and lon_min <= row[6] <= lon_max
        assert data["dict"]["geoSources"][row[7]] in {"operator", "osm", "nominatim"}
        assert data["dict"]["geoPrecisions"][row[8]] in {"exact", "address", "locality"}
    unplaced = [row for row in data["malls"] if row[5] is None]
    assert len(unplaced) == 1
    assert unplaced[0][6] is None and unplaced[0][7] == -1


def test_website_build_keeps_csp_and_tile_url_in_step(snapshot, tmp_path, monkeypatch):
    """A tile host the page's own policy blocks is a blank map with a console
    error and no other symptom, so the build derives one from the other."""
    import shutil

    from mallscape_clean import pipeline as clean_stage
    from mallscape_core import config
    from mallscape_website import pipeline as website_stage

    clean_stage.run(snapshot)
    site = tmp_path / "site"
    shutil.copytree(config.SITE_DIR, site)
    monkeypatch.setattr(config, "SITE_DIR", site)
    monkeypatch.setattr(config, "TILE_URL", "https://tiles.example.org/{z}/{x}/{y}.png")

    website_stage.run(snapshot)
    html = (site / "index.html").read_text()
    assert 'data-tiles="https://tiles.example.org/{z}/{x}/{y}.png"' in html
    assert "img-src 'self' data: https://tiles.example.org;" in html
    assert "tile.openstreetmap.org" not in html

    monkeypatch.setattr(config, "TILE_URL", "not-a-url")
    with pytest.raises(SystemExit):
        website_stage.run(snapshot)


def test_vercel_sends_no_resource_csp_of_its_own():
    """Browsers enforce the INTERSECTION of every delivered policy. A second
    CSP in vercel.json once omitted the tile host and silently blocked every
    map tile on that host, so the header may carry only what a meta tag
    cannot (frame-ancestors); resource policy lives in the page alone."""
    spec = json.loads((Path(__file__).parent.parent / "vercel.json").read_text())
    for rule in spec.get("headers", []):
        for header in rule["headers"]:
            if header["key"].lower() == "content-security-policy":
                directives = {d.strip().split()[0] for d in header["value"].split(";") if d.strip()}
                assert directives <= {"frame-ancestors"}, directives


def test_snapshot_contract_rejects_orphan_store():
    malls = MALLS.copy()
    stores = STORES.copy()
    stores.loc[0, "mall_id"] = "missing"
    with pytest.raises(ValueError, match="without a mall"):
        storage.validate_snapshot_frames(malls, stores)


def test_report_fails_loudly_without_stage1(tmp_path, monkeypatch):
    from mallscape_website import bundle

    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    with pytest.raises(SystemExit):
        bundle.build("1999-01-01")


def test_partial_scrape_does_not_drop_other_chains(snapshot, monkeypatch):
    """Re-running one chain must carry the others forward, not replace them."""
    from mallscape_scrape import pipeline as scrape_stage

    class FakeScraper:
        chain = "ayala"
        extra_headers: ClassVar[dict] = {}

        def __init__(self, fetcher):
            self.warnings = []
            self.confirmed_empty = []
            self.failed, self.alerts = {}, []

        def scrape_all(self):
            from mallscape_core.models import Mall, Store
            mall = Mall(chain="ayala", mall_id="ay-a", mall_name="Ayala A")
            return [mall], [Store(chain="ayala", mall_id="ay-a", store_name_raw="NEW")]

    monkeypatch.setattr(scrape_stage, "SCRAPERS", {"sm": object, "ayala": FakeScraper})
    malls, stores = scrape_stage.run(["ayala"], "2026-01-02", rate=1000)
    assert set(malls.chain) == {"sm", "ayala"}          # sm carried forward
    assert set(stores[stores.chain == "sm"].mall_id) == {"sm-a", "sm-b"}
    # carried rows keep their real date; only the rescraped chain is restamped
    assert set(malls[malls.chain == "sm"].scraped_at) == {"2026-01-01"}
    assert set(malls[malls.chain == "ayala"].scraped_at) == {"2026-01-02"}
    # and they keep their coordinates. Carrying forward joins two frames that
    # both count from zero, and the geocode step used to write by index label,
    # so the freshly scraped chain overwrote the carried rows sharing a label.
    carried = malls[malls.mall_id == "sm-a"].iloc[0]
    assert (carried.lat, carried.lon) == (14.55, 121.02)
    assert carried.geo_source == "operator"


def test_asset_urls_carry_a_version_that_tracks_their_contents(snapshot, tmp_path, monkeypatch):
    """Code assets keep stable names and are served with a ten minute max-age,
    so without a version in the URL a deploy leaves visitors on the previous
    release's JavaScript with no symptom. This is the guarantee the data bundle
    already gets from being content-hashed."""
    import re
    import shutil

    from mallscape_clean import pipeline as clean_stage
    from mallscape_core import config
    from mallscape_website import pipeline as website_stage

    clean_stage.run(snapshot)
    site = tmp_path / "site"
    shutil.copytree(config.SITE_DIR, site)
    monkeypatch.setattr(config, "SITE_DIR", site)

    website_stage.run(snapshot)
    html = (site / "index.html").read_text()
    versions = set(re.findall(r'[?&]v=([0-9a-f]{8})', html))
    stamped = re.search(r'data-assets="([0-9a-f]{8})"', html)
    assert stamped, "index.html carries no data-assets version"
    assert versions == {stamped.group(1)}, (versions, stamped.group(1))

    # editing any versioned asset must change every asset URL
    before = stamped.group(1)
    (site / "map.js").write_text((site / "map.js").read_text() + "\n// touched\n")
    website_stage.run(snapshot)
    after = re.search(r'data-assets="([0-9a-f]{8})"', (site / "index.html").read_text())
    assert after and after.group(1) != before


def _fake(chain, malls, *, failed=None, alerts=(), raises=None):
    """A stand-in scraper: `malls` maps each mall_id to its tenant names."""
    from mallscape_core.models import Mall, Store

    class FakeScraper:
        extra_headers: ClassVar[dict] = {}

        def __init__(self, fetcher):
            self.chain = chain
            self.warnings = [*(failed or {}).values(), *alerts]
            self.confirmed_empty = []
            self.failed, self.alerts = dict(failed or {}), list(alerts)

        def scrape_all(self):
            if raises:
                raise raises
            return (
                [Mall(chain=chain, mall_id=m, mall_name=m.upper()) for m in malls],
                [Store(chain=chain, mall_id=m, store_name_raw=n) for m, names in malls.items() for n in names],
            )

    return FakeScraper


def _fake_ayala(*, stores=("NEW",), mall_id="ay-a", **kw):
    return _fake("ayala", {mall_id: stores}, **kw)


def _scrape_ayala(monkeypatch, scraper) -> bool:
    """Scrape SM (healthy, as in the fixture) and the given Ayala, then check.
    Two chains, because a run where every chain raises writes nothing at all."""
    from mallscape_scrape import pipeline as scrape_stage

    sm = _fake("sm", {"sm-a": ("JOLLIBEE", "WATSONS"), "sm-b": ("JOLLIBEE",)})
    monkeypatch.setattr(scrape_stage, "SCRAPERS", {"sm": sm, "ayala": scraper})
    scrape_stage.run(["sm", "ayala"], "2026-01-02", rate=1000)
    return scrape_stage.check("2026-01-02")


def _problems() -> list[str]:
    health = storage.DATA_DIR / "snapshots" / "2026-01-02" / storage.SCRAPE / "health.json"
    return json.loads(health.read_text())["problems"]


def test_check_passes_a_clean_scrape(snapshot, monkeypatch):
    assert _scrape_ayala(monkeypatch, _fake_ayala())
    assert _problems() == []


@pytest.mark.parametrize(
    ("scraper", "expected"),
    [
        (_fake_ayala(raises=RuntimeError("site down")), "ayala: scrape failed entirely (RuntimeError: site down)"),
        (
            _fake_ayala(stores=(), failed={"ay-a": "FAILED ay-a: HTTPError: HTTP Error 404"}),
            "ayala: FAILED ay-a: HTTPError: HTTP Error 404",
        ),
        (_fake_ayala(alerts=["NEW mall(s) on the site not in MALLS: ['ay-b']"]), "ayala: NEW mall(s)"),
        (_fake_ayala(stores=()), "ayala:ay-a (AY-A) published no tenants and is not in empty_directories.json"),
    ],
    ids=["chain-raised", "mall-raised", "site-drift", "unexplained-empty"],
)
def test_check_fails_loudly_on_what_a_monthly_run_publishes_through(snapshot, monkeypatch, scraper, expected):
    """Each of these lets `scrape` exit 0 and the monthly run publish; the
    check is what refuses them. Exactly one problem each: a mall that raised
    is not also reported as an unexplained empty mall."""
    assert not _scrape_ayala(monkeypatch, scraper)
    problems = _problems()
    assert len(problems) == 1 and problems[0].startswith(expected), problems


def test_check_fails_on_a_chain_carried_forward(snapshot):
    from mallscape_scrape import validate

    health = validate.health(
        "2026-01-02", MALLS, STORES, chains=["sm", "ayala"], failed_chains={}, carried={"ayala"},
        failed_malls={}, alerts={},
    )
    assert health["problems"] == [
        "ayala: listings collapsed against the previous snapshot; its rows were carried forward"
    ]


def test_check_lists_a_delisted_mall_without_failing(snapshot, monkeypatch, capsys):
    """A mall leaving the operator's list is usually the real portfolio, and
    would fail every week until the next snapshot; it is shown, not failed."""
    assert _scrape_ayala(monkeypatch, _fake_ayala(mall_id="ay-b"))
    assert "malls no longer listed since 2026-01-01: ['ay-a']" in capsys.readouterr().out


def test_check_fails_when_the_scrape_never_finished(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from mallscape.cli import app

    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    result = CliRunner().invoke(app, ["check", "--date", "2026-05-05"])
    assert result.exit_code == 1
    assert "no health record for 2026-05-05" in result.output
    assert not (tmp_path / "snapshots" / "2026-05-05").exists()


def test_a_rerun_that_dies_leaves_no_clean_record_behind(snapshot, monkeypatch):
    """Otherwise `check` vouches for the earlier, clean attempt."""
    from mallscape_scrape import pipeline as scrape_stage

    assert _scrape_ayala(monkeypatch, _fake_ayala())
    down = _fake("sm", {}, raises=RuntimeError("down"))
    monkeypatch.setattr(scrape_stage, "SCRAPERS", {"sm": down, "ayala": _fake_ayala(raises=RuntimeError("down"))})
    with pytest.raises(SystemExit, match="every chain failed"):
        scrape_stage.run(["sm", "ayala"], "2026-01-02", rate=1000)
    assert not scrape_stage.check("2026-01-02")


def test_a_one_chain_run_says_which_chains_it_did_not_check(snapshot, monkeypatch, capsys):
    from mallscape_scrape import pipeline as scrape_stage

    monkeypatch.setattr(scrape_stage, "SCRAPERS", {"sm": object, "ayala": _fake_ayala()})
    scrape_stage.run(["ayala"], "2026-01-02", rate=1000)
    assert scrape_stage.check("2026-01-02")
    assert "not scraped in this run, so not checked: ['sm']" in capsys.readouterr().out
    health = storage.DATA_DIR / "snapshots" / "2026-01-02" / storage.SCRAPE / "health.json"
    assert json.loads(health.read_text())["chains"] == ["ayala"]


def test_an_alert_the_live_retry_answered_does_not_fail_the_check():
    """An empty mall is re-asked against the live site. When that answer has
    tenants, the empty attempt's alert ("served none") was superseded: it
    stays a warning but is no longer a problem."""
    import contextlib

    from mallscape_core.models import Mall, Store
    from mallscape_scrape.scrapers.base import MallChainScraper

    class Flaky(MallChainScraper):
        chain = "sm"
        attempts = 0

        def discover_malls(self):
            return [Mall(chain="sm", mall_id="sm-a", mall_name="SM A")]

        def scrape_mall(self, mall):
            Flaky.attempts += 1
            if Flaky.attempts == 1:
                self.alert("sm-a: API reports 1 tenants but served none")
                return []
            return [Store(chain="sm", mall_id="sm-a", store_name_raw="JOLLIBEE")]

    class Fetcher:
        def bypass_cache(self):
            return contextlib.nullcontext()

    scraper = Flaky(Fetcher())
    _, stores = scraper.scrape_all()
    assert len(stores) == 1
    assert scraper.alerts == []
    assert any("served none" in w for w in scraper.warnings)


def test_an_unreadable_fisher_mall_floor_list_is_an_alert():
    """The floor tabs are the roster check: falling back to the hardcoded
    floors still publishes, but a new floor would go unseen."""
    from curl_cffi.requests.exceptions import HTTPError

    from mallscape_scrape.scrapers.fishermall import FishermallScraper

    class Fetcher:
        def __init__(self, page):
            self.page = page

        def get_text(self, url, params=None):
            if self.page is None:
                raise HTTPError("HTTP Error 403")
            return self.page

    unreadable = FishermallScraper(Fetcher(None))
    unreadable.discover_malls()
    assert any("could not read floor tabs" in a for a in unreadable.alerts)
    redesigned = FishermallScraper(Fetcher("<html><body>new layout</body></html>"))
    redesigned.discover_malls()
    assert any("no floor tabs found" in a for a in redesigned.alerts)



def _ci_scrape(monkeypatch, scrapers: dict, *, skip=()) -> list[int]:
    """Scrape the way CI does: one `scrape-part` per chain, then `assemble`.
    Chains in `skip` never report, as when their job dies. Returns the
    scrape-part exit codes."""
    from typer.testing import CliRunner

    from mallscape import cli
    from mallscape_scrape import pipeline as scrape_stage

    monkeypatch.setattr(scrape_stage, "SCRAPERS", scrapers)
    monkeypatch.setattr(cli, "SCRAPERS", scrapers)
    runner = CliRunner()
    codes = [
        runner.invoke(cli.app, ["scrape-part", "--chain", name, "--date", "2026-01-02", "--rate", "1000"]).exit_code
        for name in scrapers if name not in skip
    ]
    result = runner.invoke(cli.app, ["assemble", "--date", "2026-01-02"])
    assert result.exit_code == 0, result.output
    return codes


def _stage1_files(root: Path) -> dict[str, str]:
    stage = root / "snapshots" / "2026-01-02" / storage.SCRAPE
    return {p.name: p.read_text() for p in sorted(stage.iterdir()) if p.suffix != ".parquet"}


def test_scraping_chain_by_chain_builds_the_same_snapshot_as_one_run(tmp_path, monkeypatch):
    """CI scrapes each chain in its own job and assembles after; the result
    has to be the snapshot a single `mallscape scrape` would have written,
    down to the report and the health record."""
    from mallscape_scrape import pipeline as scrape_stage

    scrapers = {
        "sm": _fake("sm", {"sm-a": ("JOLLIBEE", "WATSONS"), "sm-b": ("JOLLIBEE",)}),
        "ayala": _fake_ayala(failed={"ay-b": "FAILED ay-b: X"}, alerts=["roster changed"]),
    }
    built = {}
    for how in ("run", "ci"):
        root = tmp_path / how
        monkeypatch.setattr(storage, "DATA_DIR", root)
        storage.write("2026-01-01", storage.SCRAPE, "malls", MALLS)
        storage.write("2026-01-01", storage.SCRAPE, "stores", STORES)
        if how == "run":
            monkeypatch.setattr(scrape_stage, "SCRAPERS", scrapers)
            scrape_stage.run(list(scrapers), "2026-01-02", rate=1000)
        else:
            assert _ci_scrape(monkeypatch, scrapers) == [0, 0]
        built[how] = _stage1_files(root)
    assert built["ci"] == built["run"]
    assert set(built["ci"]) == {"health.json", "malls.csv", "run_report.md", "stores.csv"}


def test_a_chain_whose_part_never_arrived_counts_as_failed(snapshot, monkeypatch):
    """Its job died before writing even a failure. Assembling without it must
    not read as that chain having no malls."""
    sm = _fake("sm", {"sm-a": ("JOLLIBEE", "WATSONS"), "sm-b": ("JOLLIBEE",)})
    _ci_scrape(monkeypatch, {"sm": sm, "ayala": _fake_ayala()}, skip=("ayala",))
    problems = _problems()
    assert any("ayala" in p and "no result" in p for p in problems), problems


def test_a_chain_that_fails_outright_exits_1_and_still_reports(snapshot, monkeypatch):
    from mallscape_scrape import pipeline as scrape_stage

    sm = _fake("sm", {"sm-a": ("JOLLIBEE", "WATSONS"), "sm-b": ("JOLLIBEE",)})
    down = _fake_ayala(raises=RuntimeError("tunnel to http://user:hunter2@proxy failed"))
    assert _ci_scrape(monkeypatch, {"sm": sm, "ayala": down}) == [0, 1]
    part = json.loads(scrape_stage.part_path("2026-01-02", "ayala").read_text())
    assert "RuntimeError" in part["error"] and "hunter2" not in part["error"]
    assert any("ayala" in p and "RuntimeError" in p for p in _problems())


def test_the_ci_matrix_lists_every_chain_once_and_flags_the_proxied_ones():
    from typer.testing import CliRunner

    from mallscape.cli import app
    from mallscape_core import config
    from mallscape_scrape.registry_of_scrapers import SCRAPERS

    result = CliRunner().invoke(app, ["chains"])
    matrix = json.loads(result.output)
    assert [m["chain"] for m in matrix] == list(SCRAPERS)
    assert {m["chain"] for m in matrix if m["proxy"]} == set(config.PROXY_CHAINS) & set(SCRAPERS)
