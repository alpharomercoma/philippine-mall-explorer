"""Parser regression tests against captured fixture pages (2026-07-26).

If a site redesign breaks a parser, these tests keep working (fixtures are
frozen) - the live validation report is what flags the redesign. These tests
protect against parser regressions while refactoring.
"""

import contextlib
import json
from collections import Counter
from pathlib import Path
from typing import ClassVar

import pytest

from mallscape_clean.normalize import brand_key
from mallscape_core.geo import parse_coords
from mallscape_core.models import Mall
from mallscape_scrape import geocode, validate
from mallscape_scrape.scrapers.ayala import derive_region
from mallscape_scrape.scrapers.filinvest import FilinvestScraper
from mallscape_scrape.scrapers.robinsons import RobinsonsScraper, _norm_key
from mallscape_scrape.scrapers.starmall import StarmallScraper

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def scraper():
    s = RobinsonsScraper.__new__(RobinsonsScraper)
    s.warnings = []
    return s


@pytest.fixture
def mall():
    return Mall(chain="robinsons", mall_id="test", mall_name="Test")


class TestDrupalParser:
    def test_malolos_full_directory(self, scraper, mall):
        html = (FIXTURES / "rob-malolos.html").read_text()
        stores = scraper._parse_drupal(mall, html)
        assert len(stores) == 204
        assert {s.floor for s in stores} == {"Level 1", "Level 2", "Level 3", "Level 4"}

    def test_phone_split(self, scraper, mall):
        html = (FIXTURES / "rob-malolos.html").read_text()
        stores = scraper._parse_drupal(mall, html)
        bonchon = next(s for s in stores if s.store_name_raw == "Bonchon")
        assert bonchon.phone == "044-794-3116"
        assert bonchon.floor == "Level 1"
        no_phone = next(s for s in stores if s.store_name_raw == "Argentee")
        assert no_phone.phone is None

    def test_manila_large_mall(self, scraper, mall):
        html = (FIXTURES / "rob-manila.html").read_text()
        stores = scraper._parse_drupal(mall, html)
        assert len(stores) > 600

    def test_galleria_non_level_floors(self, scraper, mall):
        # flagship mall using basement/upper-ground/lower-ground field names
        html = (FIXTURES / "rob-galleria.html").read_text()
        stores = scraper._parse_drupal(mall, html)
        assert len(stores) == 404
        floors = {s.floor for s in stores}
        assert any("asement" in (f or "") for f in floors)
        assert mall.address is not None


class TestVMDParser:
    def test_plaza_categories_and_floors(self, scraper, mall):
        html = (FIXTURES / "vmd-plaza.html").read_text()
        stores = scraper._parse_vmd(mall, html)
        assert len(stores) == 19
        by_cat = {}
        for s in stores:
            by_cat.setdefault(s.category, []).append(s)
        assert set(by_cat) == {"shop", "dine", "recharge"}
        greenwich = next(s for s in stores if s.store_name_raw == "GREENWICH")
        assert greenwich.category == "dine"
        assert greenwich.floor == "Ground Floor"

    def test_no_header_junk(self, scraper, mall):
        html = (FIXTURES / "vmd-plaza.html").read_text()
        stores = scraper._parse_vmd(mall, html)
        names = [s.store_name_raw for s in stores]
        assert not any("10AM" in n or "Daily" in n for n in names)

    def test_manila_scale(self, scraper, mall):
        html = (FIXTURES / "vmd-manila.html").read_text()
        stores = scraper._parse_vmd(mall, html)
        assert len(stores) > 550
        assert any(s.category == "lingkod pinoy" for s in stores)


class TestNormalize:
    def test_case_and_punctuation(self):
        assert brand_key("UNIQLO") == brand_key("Uniqlo")
        assert brand_key("Conti's") == brand_key("CONTIS")

    def test_phone_leftover(self):
        assert brand_key("Bonchon | 044-794-3116") == "bonchon"

    def test_branch_suffix(self):
        assert brand_key("BDO - ATM") == "bdo atm"
        assert brand_key("Potato Corner (Center Atrium)") == "potato corner"

    def test_branch_suffix_survives_fancy_dashes(self):
        # The ascii fold deletes en and em dashes outright; without an earlier
        # fold to a hyphen, the dashed spelling of a kiosk suffix quietly
        # became its own brand.
        assert brand_key("Starbucks \u2014 Kiosk") == "starbucks"
        assert brand_key("Starbucks \u2013 Kiosk") == "starbucks"
        assert brand_key("Starbucks - Kiosk") == "starbucks"

    def test_aliases(self):
        assert brand_key("McDo") == brand_key("McDonald's")
        assert brand_key("BDO Unibank") == brand_key("BDO")


class TestRegistryMatching:
    def test_norm_key_strips_chain_words(self):
        assert _norm_key("Robinsons Place Malolos") == _norm_key("Malolos")
        assert _norm_key("Robinsons Town Mall Malabon") == _norm_key("Malabon")


class TestAyalaRegions:
    """Region derivation is the only inference in the Ayala path (its API
    publishes no region), so it carries the regression tests."""

    @pytest.mark.parametrize(
        "text,lat,lon,expected",
        [
            # provincial place names appear as MM street names - MM must win
            ("Greenbelt Mall, Legazpi Street, Makati City", 14.55, 121.02, "metro-manila"),
            ("Ayala Malls Legazpi, Legazpi City, Albay 4500", 13.15, 123.75, "south-luzon"),
            # "Rizal Highway" must not be read as Rizal province
            ("Harbor Point, Subic Bay Freeport Zone, 2200 Zambales", 14.83, 120.28, "north-luzon"),
            ("Trinoma EDSA cor. North Avenue, QC", 14.65, 121.03, "metro-manila"),
            ("Vertis North, Brgy. Bagong Pag-asa, Q.C.", 14.65, 121.04, "metro-manila"),
            # placeholder coordinates (1.001, 1.001) - address must carry it
            ("Ayala Pavilion Mall Bldg. A, Binan, Laguna", 1.001, 1.001, "south-luzon"),
            ("Serin, Silang Crossing East Tagaytay City, Cavite", 14.11, 120.26, "south-luzon"),
            ("Centrio Mall, Cagayan de Oro City 9000", 8.48, 124.65, "mindanao"),
            ("Ayala Center Cebu, Cebu Business Park, Cebu City", 10.32, 123.91, "visayas"),
            ("MarQuee Mall, Angeles City, Pampanga 2009", 15.16, 120.61, "north-luzon"),
        ],
    )
    def test_region_derivation(self, text, lat, lon, expected):
        assert derive_region(text, lat, lon) == expected

    def test_coordinate_fallback_when_address_unhelpful(self):
        assert derive_region("Some New Mall", 10.3, 123.9) == "visayas"

    def test_unknown_when_no_signal(self):
        assert derive_region("Some New Mall", None, None) is None

    def test_smdc_is_not_a_geographic_region(self):
        from mallscape_scrape.scrapers.sm import public_region

        assert public_region("smdc") is None
        assert public_region("metro-manila") == "metro-manila"


class TestAyalaFixtures:
    def test_all_malls_present(self):
        malls = json.loads((FIXTURES / "ayala-malls.json").read_text())
        assert len(malls) == 32
        assert {m["slugName"] for m in malls} >= {"ayala-glorietta", "ayala-trinoma"}

    def test_store_categories_sum_to_total(self):
        stores = json.loads((FIXTURES / "ayala-stores-abreeza.json").read_text())
        assert len(stores) == 297
        cats = Counter(s["category"] for s in stores)
        assert set(cats) == {"shop", "dine", "services", "essentials", "entertainment"}
        assert sum(cats.values()) == 297


class TestFilinvestParser:
    def test_festival_mall_full_table(self):
        s = FilinvestScraper.__new__(FilinvestScraper)
        s.warnings = []
        mall = Mall(chain="filinvest", mall_id="festival-mall", mall_name="Festival Mall")
        html = (FIXTURES / "fil-festival.html").read_text()
        stores = s.scrape_mall.__wrapped__(s, mall, html) if hasattr(
            s.scrape_mall, "__wrapped__"
        ) else _filinvest_parse(s, mall, html)
        assert len(stores) == 787
        # category header rows must propagate down to following rows
        acme = next(x for x in stores if x.store_name_raw == "Acme Jewelry")
        assert acme.category == "accessories"
        assert acme.floor == "Upper Ground Floor, West Wing"
        assert all(x.category for x in stores[:50])


def _filinvest_parse(scraper, mall, html):
    """Drive FilinvestScraper's table parsing against fixture HTML."""
    from unittest.mock import Mock

    scraper.fetcher = Mock()
    scraper.fetcher.get_text.return_value = html
    return scraper.scrape_mall(mall)


class TestStarmallParser:
    def test_alabang_gallery_blob(self):
        from unittest.mock import Mock

        s = StarmallScraper.__new__(StarmallScraper)
        s.warnings = []
        s.fetcher = Mock()
        s.fetcher.get_text.return_value = (FIXTURES / "starmall-alabang.html").read_text()
        mall = Mall(chain="starmall", mall_id="alabang", mall_name="Starmall Alabang")
        stores = s.scrape_mall(mall)
        assert len(stores) > 100
        names = {x.store_name_raw for x in stores}
        assert "ALL BANK" in names
        allbank = next(x for x in stores if x.store_name_raw == "ALL BANK")
        assert allbank.phone == "8842-7099"
        assert allbank.floor == "Level 2"


class TestWaltermartParser:
    def test_category_page_data_attributes(self):
        from selectolax.parser import HTMLParser

        html = (FIXTURES / "waltermart-category.html").read_text()
        nodes = HTMLParser(html).css("a.wm-store")
        names = [n.attributes.get("data-name") for n in nodes]
        assert "ADDAS" in names
        assert len(names) >= 10


class TestWaltermartIndex:
    """The chain-wide store index inverted through the branches API, which is
    the uncapped source; the per-mall category pages cap at 10 per category."""

    class FakeFetcher:
        def __init__(self):
            self.calls = []

        def get_text(self, url, **kw):
            self.calls.append(url)
            if url.endswith("/stores/"):
                return (
                    '<a class="wm-store" data-id="1" data-name="Chatime"></a>'
                    '<a class="wm-store" data-id="2" data-name="Jollibee"></a>'
                )
            if "/stores/food-choices/" in url:
                return '<a class="wm-store" data-id="2" data-name="Jollibee"></a>'
            if "/stores/" in url:
                return ""
            raise AssertionError(f"unexpected fetch {url}")

        def get_json(self, url, **kw):
            self.calls.append(url)
            if url.endswith("/api/stores/1/"):
                return [{"slug": "makati"}, {"slug": "sucat"}]
            if url.endswith("/api/stores/2/"):
                return [{"slug": "makati"}]
            raise AssertionError(f"unexpected fetch {url}")

    def make(self):
        from mallscape_scrape.scrapers.waltermart import WaltermartScraper

        s = WaltermartScraper.__new__(WaltermartScraper)
        s.warnings = []
        s.fetcher = self.FakeFetcher()
        return s

    def test_stores_come_from_the_branch_api_not_the_capped_pages(self):
        s = self.make()
        makati = s.scrape_mall(Mall(chain="waltermart", mall_id="makati", mall_name="M"))
        assert sorted(x.store_name_raw for x in makati) == ["Chatime", "Jollibee"]
        assert all("/malls/" not in c for c in s.fetcher.calls)

    def test_category_rides_along_and_absence_is_none(self):
        s = self.make()
        makati = s.scrape_mall(Mall(chain="waltermart", mall_id="makati", mall_name="M"))
        by_name = {x.store_name_raw: x.category for x in makati}
        assert by_name["Jollibee"] == "food choices"
        assert by_name["Chatime"] is None

    def test_the_index_is_built_once_for_the_whole_chain(self):
        s = self.make()
        s.scrape_mall(Mall(chain="waltermart", mall_id="makati", mall_name="M"))
        n = len(s.fetcher.calls)
        sucat = s.scrape_mall(Mall(chain="waltermart", mall_id="sucat", mall_name="S"))
        assert len(s.fetcher.calls) == n
        assert [x.store_name_raw for x in sucat] == ["Chatime"]

    def test_a_mall_no_store_claims_is_rechecked_through_its_own_pages(self):
        s = self.make()
        calls = s.fetcher.calls

        def get_text(url, **kw):
            calls.append(url)
            if "/malls/silang/" in url:
                return ""
            return type(s.fetcher).get_text(s.fetcher, url, **kw)

        s.fetcher.get_text = get_text
        empty = s.scrape_mall(Mall(chain="waltermart", mall_id="silang", mall_name="X"))
        assert empty == []
        assert any("/malls/silang/" in c for c in calls)


class TestCollapseGuard:
    def frame(self, chain, n):
        import pandas as pd

        return pd.DataFrame({"chain": [chain] * n, "mall_id": ["m"] * n})

    def test_a_halved_chain_stops_the_run(self, tmp_path, monkeypatch):
        import pandas as pd

        from mallscape_scrape import pipeline

        monkeypatch.setattr(
            pipeline.storage, "previous_run", lambda run_date: "2026-01-01"
        )
        monkeypatch.setattr(
            pipeline.storage, "read", lambda *a: self.frame("araneta", 300)
        )
        with pytest.raises(SystemExit, match="araneta: 300 -> 10"):
            pipeline.guard_against_collapse("2026-02-01", self.frame("araneta", 10))
        # the escape hatch is explicit and per-chain
        monkeypatch.setenv("MALLSCAPE_ACCEPT_COLLAPSE", "araneta")
        pipeline.guard_against_collapse("2026-02-01", self.frame("araneta", 10))
        # a small chain shrinking is tolerated, but vanishing outright is not
        monkeypatch.delenv("MALLSCAPE_ACCEPT_COLLAPSE")
        monkeypatch.setattr(
            pipeline.storage, "read", lambda *a: self.frame("tiny", 30)
        )
        pipeline.guard_against_collapse("2026-02-01", self.frame("tiny", 10))
        with pytest.raises(SystemExit, match="tiny: 30 -> 0"):
            pipeline.guard_against_collapse("2026-02-01", self.frame("tiny", 0))
        # and a first run has nothing to compare against
        monkeypatch.setattr(pipeline.storage, "previous_run", lambda run_date: None)
        pipeline.guard_against_collapse(
            "2026-02-01", pd.DataFrame({"chain": [], "mall_id": []})
        )


class TestAranetaParser:
    def test_ali_mall_gallery_items(self):
        from unittest.mock import Mock

        from mallscape_scrape.scrapers.araneta import AranetaScraper

        s = AranetaScraper.__new__(AranetaScraper)
        s.warnings = []
        s.fetcher = Mock()
        s.fetcher.get_text.return_value = (FIXTURES / "araneta-ali-mall.html").read_text()
        mall = Mall(chain="araneta", mall_id="ali-mall", mall_name="Ali Mall", extra={"slug": "ali-mall"})
        stores = s.scrape_mall(mall)
        # must match the raw gallery-item count exactly (no silent dedupe)
        assert len(stores) == 88
        handyman = next(x for x in stores if x.store_name_raw == "HANDYMAN")
        assert handyman.floor == "LGF"


class TestSnapshotIntegrity:
    """Guards against the partial-snapshot failure: a crashed or single-chain
    run must never be published as `latest` or silently analyzed."""

    def _snapshot(self, tmp_path, monkeypatch, malls_df, stores_df, date="2026-01-01"):
        from mallscape_core import storage

        monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
        storage.write(date, storage.SCRAPE, "malls", malls_df)
        storage.write(date, storage.SCRAPE, "stores", stores_df)
        return storage

    def test_empty_snapshot_is_not_usable(self, tmp_path, monkeypatch):
        import pandas as pd

        storage = self._snapshot(
            tmp_path, monkeypatch,
            pd.DataFrame({"scraped_at": []}), pd.DataFrame({"scraped_at": []}),
        )
        assert storage.is_usable("2026-01-01") is False

    def test_update_latest_refuses_empty(self, tmp_path, monkeypatch):
        import pandas as pd
        import pytest as _pytest

        storage = self._snapshot(
            tmp_path, monkeypatch,
            pd.DataFrame({"scraped_at": []}), pd.DataFrame({"scraped_at": []}),
        )
        with _pytest.raises(ValueError, match="refusing to publish"):
            storage.publish_latest("2026-01-01")

    def test_latest_usable_skips_broken_newer_snapshot(self, tmp_path, monkeypatch):
        import pandas as pd

        good_m = pd.DataFrame({"chain": ["sm"], "mall_id": ["x"], "scraped_at": ["2026-01-01"]})
        good_s = pd.DataFrame({"chain": ["sm"], "mall_id": ["x"], "store_name_raw": ["Y"]})
        storage = self._snapshot(tmp_path, monkeypatch, good_m, good_s, "2026-01-01")
        # a newer but empty snapshot must be skipped, not selected
        storage.write("2026-01-02", storage.SCRAPE, "malls", pd.DataFrame({"scraped_at": []}))
        storage.write("2026-01-02", storage.SCRAPE, "stores", pd.DataFrame({"scraped_at": []}))
        assert storage.latest_usable_run() == "2026-01-01"


class TestAuditRegressions:
    """Defects found by the completeness audit - each must stay fixed."""

    def test_starmall_decodes_all_unicode_escapes(self):
        from unittest.mock import Mock
        s = StarmallScraper.__new__(StarmallScraper)
        s.warnings = []
        s.fetcher = Mock()
        s.fetcher.get_text.return_value = (FIXTURES / "starmall-alabang.html").read_text()
        mall = Mall(chain="starmall", mall_id="alabang", mall_name="Starmall Alabang")
        names = [x.store_name_raw for x in s.scrape_mall(mall)]
        # apostrophes arrive as ' in the JSON blob and must be decoded,
        # otherwise brand_key produces "baker u0027s fair"
        assert not any("\\u00" in n for n in names)
        assert "BAKER'S FAIR" in names

    def test_names_ending_in_a_period_survive(self):
        from mallscape_clean.normalize import brand_key
        # "INC." / "CORP." / "ACC." are real tenant suffixes, not noise. A
        # trailing-period filter once dropped every one of them.
        assert brand_key("SIETE ESTRELLAS, INC.") != ""

    def test_sm_dedupe_key_separates_distinct_outlets(self):
        """Two outlets of one brand on different floors must both survive."""
        keys = set()
        for floor, building in [("2F", "MAIN"), ("GF", "EXPANSION")]:
            keys.add(("", "POTATO CORNER", floor, building))
        assert len(keys) == 2


class TestReportDeterminism:
    def test_report_is_byte_identical_across_runs(self, tmp_path, monkeypatch):
        import pandas as pd

        from mallscape_core import storage
        from mallscape_report import report

        monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
        malls = pd.DataFrame({
            "chain": ["sm", "ayala"], "mall_id": ["a", "b"],
            "mall_name": ["A Mall", "B Mall"], "region": ["metro-manila", "visayas"],
            "property_type": ["mall", "mall"], "scraped_at": ["2026-01-01"] * 2,
        })
        stores = pd.DataFrame({
            "chain": ["sm", "sm", "ayala"], "mall_id": ["a", "a", "b"],
            "store_name_raw": ["X", "Y", "Z"],
        })
        storage.write("2026-01-01", storage.SCRAPE, "malls", malls)
        storage.write("2026-01-01", storage.SCRAPE, "stores", stores)
        first = report.build("2026-01-01")
        second = report.build("2026-01-01")
        assert first == second
        # and it must actually contain the numbers, not just be stable-empty
        assert "3" in first and "A Mall" in first


class TestCleanStage:
    """Stage 2 must standardize without inventing or destroying data."""

    def test_is_non_destructive(self):
        import pandas as pd

        from mallscape_clean import clean

        raw = pd.DataFrame({
            "chain": ["sm"], "mall_id": ["a"], "store_name_raw": ["POTATO CORNER"],
            "category": ["dining"], "floor": ["2ND FLOOR"], "building": [None],
            "phone": ["0917-123-4567"], "source": ["sm-api"], "scraped_at": ["2026-01-01"],
        })
        before = raw.copy(deep=True)
        out = clean.build(raw)
        pd.testing.assert_frame_equal(raw, before)          # input untouched
        assert out.loc[0, "store_name_raw"] == "POTATO CORNER"  # raw preserved
        assert out.loc[0, "store_name"] == "Potato Corner"
        assert out.loc[0, "floor_level"] == 2
        assert out.loc[0, "phone_e164"] == "+639171234567"

    def test_floor_levels(self):
        from mallscape_clean.clean import standardize_floor
        cases = {
            "2F": 2, "Level 3": 3, "2nd Floor": 2, "SECOND FLOOR": 2,
            "Ground": 0, "GF": 0, "LGF": -1, "Lower Ground": -1,
            "Basement 2": -2, "UGF": 1,
        }
        for raw, level in cases.items():
            assert standardize_floor(raw)[1] == level, raw
        # places, not storeys - must not be assigned a level
        for raw in ["Kiosk", "Food Hall", "Roof Deck", "Parkway"]:
            assert standardize_floor(raw)[1] is None, raw

    def test_category_harmonization_across_chains(self):
        from mallscape_clean.clean import standardize_category
        for raw in ["dining", "dine", "Food Choices", "DINING / FOOD (KIOSK / CARTS)"]:
            assert standardize_category(raw) == "dining", raw
        for raw in ["cyberzone", "cybermart", "gadgets", "telecoms / computers / electronics"]:
            assert standardize_category(raw) == "electronics", raw
        # meaningless upstream values must not be forced into a bucket
        for raw in ["1", "4", "undefined", "all", None]:
            assert standardize_category(raw) == "unknown", raw

    def test_phone_e164(self):
        from mallscape_clean.clean import to_e164
        assert to_e164("0917-123-4567") == "+639171234567"
        assert to_e164("8354-1053 / 8354-1018") is None   # landline, no area code
        assert to_e164("(02) 8 462 8888") == "+63284628888"
        assert to_e164(None) is None

    def test_strips_only_genuine_name_noise(self):
        """Phones and status markers go; meaningful parentheticals stay."""
        from mallscape_clean.clean import clean_name

        assert clean_name("ACE Fashion 9209267708") == "ACE Fashion"
        assert clean_name("ANYTIME FITNESS (Temporarily Closed)") == "Anytime Fitness"
        assert clean_name("Alkimia By Mumbakki (0946-138-4463)") == "Alkimia By Mumbakki"
        # a parenthetical that identifies a sub-brand must survive
        assert clean_name("Executive Optical (Fun Optics)") == "Executive Optical (Fun Optics)"
        # a number that IS the name must survive
        assert clean_name("205") == "205"

    def test_brand_matching_preserves_meaningful_parentheticals(self):
        from mallscape_clean.normalize import brand_key

        assert brand_key("Executive Optical (Fun Optics)") == "executive optical (fun optics)"
        assert brand_key("Executive Optical (Center Atrium)") == "executive optical"
        assert brand_key("BPI (ATM)") == "bpi atm"

    def test_preserves_acronyms(self):
        from mallscape_clean.clean import clean_name

        for acronym in ("CLN", "PLDT", "PNB", "LBC", "BBQ", "BDO"):
            assert clean_name(acronym) == acronym
        # vowel-less words are not acronyms
        assert clean_name("SKY RANCH") == "Sky Ranch"
        assert clean_name("MY CUP") == "My Cup"
        # Mc keeps its internal capital
        assert clean_name("MCDONALD'S") == "McDonald's"

    def test_atm_is_a_distinct_tenant_identity(self):
        from mallscape_clean.clean import brand_key, store_format

        assert store_format("BPI (ATM)") == "atm"
        assert store_format("BPI") == "standard"
        assert store_format("Potato Corner (Kiosk)") == "kiosk"
        assert store_format("Jollibee Drive Thru") == "drive-thru"
        assert brand_key("BPI (ATM)") != brand_key("BPI")

    def test_deterministic(self):
        import pandas as pd

        from mallscape_clean import clean
        raw = pd.DataFrame({
            "chain": ["sm", "ayala"], "mall_id": ["a", "b"],
            "store_name_raw": ["B STORE", "A STORE"], "category": ["dine", "shop"],
            "floor": ["2F", None], "building": [None, None], "phone": [None, None],
            "source": ["x", "y"], "scraped_at": ["2026-01-01"] * 2,
        })
        assert clean.build(raw).equals(clean.build(raw))


class TestWebsiteStage:
    def test_bundle_is_deterministic_and_compact(self, tmp_path, monkeypatch):
        import pandas as pd

        from mallscape_core import storage
        from mallscape_website import bundle as website_bundle

        monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
        storage.write("2026-01-01", storage.SCRAPE, "malls", pd.DataFrame({
            "chain": ["sm"], "mall_id": ["a"], "mall_name": ["A Mall"],
            "region": ["metro-manila"], "property_type": ["mall"],
            "scraped_at": ["2026-01-01"],
        }))
        storage.write("2026-01-01", storage.CLEAN, "stores_clean", pd.DataFrame({
            "chain": ["sm"], "mall_id": ["a"], "store_name_raw": ["X STORE"],
            "store_name": ["X Store"], "brand_key": ["x store"],
            "brand_canonical": ["x store"], "category_std": ["shopping"],
        }))

        digest, first = website_bundle.build("2026-01-01")
        digest2, second = website_bundle.build("2026-01-01")
        assert digest == digest2
        assert first == second
        assert first["schema"] == 4
        assert first["brandCategories"] == [[0]]
        assert first["totals"]["properties"] == 1
        # edges are flat pairs, so the length is always even
        assert len(first["edges"]) % 2 == 0

    def test_a_property_with_no_tenants_is_left_out_and_counted(self, tmp_path, monkeypatch):
        """A pin whose popup would be empty answers no question anyone can ask
        of a brand explorer. It is left out - and said out loud, because a
        count the page cannot explain is worse than a count that is short."""
        import pandas as pd

        from mallscape_core import storage
        from mallscape_website import bundle as website_bundle

        monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
        storage.write("2026-01-01", storage.SCRAPE, "malls", pd.DataFrame({
            "chain": ["sm", "sm"], "mall_id": ["a", "empty"],
            "mall_name": ["A Mall", "Empty Mall"],
            "region": ["metro-manila", "metro-manila"],
            "property_type": ["mall", "mall"],
            "scraped_at": ["2026-01-01", "2026-01-01"],
        }))
        storage.write("2026-01-01", storage.CLEAN, "stores_clean", pd.DataFrame({
            "chain": ["sm"], "mall_id": ["a"], "store_name_raw": ["X STORE"],
            "store_name": ["X Store"], "brand_key": ["x store"],
            "brand_canonical": ["x store"], "category_std": ["shopping"],
        }))

        _, built = website_bundle.build("2026-01-01")
        assert built["totals"]["properties"] == 1
        assert [row[0] for row in built["malls"]] == ["A Mall"]
        assert built["quality"]["withheldProperties"] == 1


class TestGeocoding:
    """Both bugs these cover shipped once and were caught by inspecting output,
    not by a failing test. They are pinned here so they cannot come back."""

    SM_BACOOR: ClassVar[dict] = {"id": "way/1", "names": ["SM City Bacoor"], "lat": 14.4452, "lon": 120.9504}
    SM_STORE_FAR: ClassVar[dict] = {"id": "way/2", "names": ["SM Store"], "lat": 7.0496, "lon": 125.5881}
    SM_STORE_NEAR: ClassVar[dict] = {"id": "way/3", "names": ["SM Store"], "lat": 14.3928, "lon": 120.8509}

    def test_shorter_name_is_not_a_match(self):
        # "SM Store" shares every one of its tokens with "SM City Bacoor".
        # Treating that as containment let branch supermarkets outscore malls.
        assert geocode.score("SM City Bacoor", "SM Store") < 0.90

    def test_longer_name_containing_ours_is_a_match(self):
        assert geocode.score("SM City Baguio", "SM City Baguio Annex") >= 0.90

    def test_exact_name_survives_a_disagreeing_region(self):
        # Bacoor is in Cavite, so its region is south-luzon, but its
        # coordinates fall inside the coarse Metro Manila box. The name is the
        # stronger evidence and has to win, or the mall goes unplaced.
        assert geocode.derive_region("", 14.4452, 120.9504) == "metro-manila"
        hit, reason = geocode.best_match(
            "SM City Bacoor", "south-luzon",
            [self.SM_BACOOR, self.SM_STORE_FAR, self.SM_STORE_NEAR],
        )
        assert reason == ""
        assert hit["id"] == "way/1"

    def test_fuzzy_name_in_the_wrong_region_is_rejected(self):
        hit, reason = geocode.best_match(
            "Gaisano Grand Cebu", "visayas",
            [{"id": "way/9", "names": ["Gaisano Grand Cebux"], "lat": 7.05, "lon": 125.58}],
        )
        assert hit is None and reason

    def test_two_exact_matches_far_apart_are_ambiguous(self):
        twin = {"id": "way/4", "names": ["SM City Bacoor"], "lat": 10.3, "lon": 123.9}
        hit, reason = geocode.best_match("SM City Bacoor", None, [self.SM_BACOOR, twin])
        assert hit is None
        assert "ambiguous" in reason

    def test_coordinates_outside_the_country_are_rejected(self):
        assert parse_coords(51.5, -0.12) is None      # London
        assert parse_coords("14.55", "121.02") == (14.55, 121.02)
        assert parse_coords(None, None) is None
        assert parse_coords("", "") is None

    def test_attach_is_idempotent_and_registry_owned(self, monkeypatch):
        import pandas as pd

        monkeypatch.setattr(geocode, "load", lambda: {
            "sm:a": {"lat": 14.5, "lon": 121.0, "source": "osm", "precision": "exact"},
        })
        frame = pd.DataFrame({
            "chain": ["sm", "sm", "ayala"],
            "mall_id": ["a", "b", "c"],
            # b carries a stale coordinate from an earlier run; the registry no
            # longer vouches for it, so attach must drop it rather than keep it.
            "lat": [None, 9.99, 7.09],
            "lon": [None, 99.9, 125.6],
            "geo_source": [None, "osm", "operator"],
            "geo_precision": [None, "exact", "exact"],
        })
        once, missing = geocode.attach(frame)
        assert missing == ["sm:b"]
        assert once.loc[0, "lat"] == 14.5
        assert pd.isna(once.loc[1, "lat"])
        assert once.loc[2, "lat"] == 7.09          # operator coordinates untouched
        twice, missing_again = geocode.attach(once)
        assert missing == missing_again
        assert twice.equals(once)

    def test_attach_writes_to_rows_not_to_index_labels(self, monkeypatch):
        """A carried-forward frame has repeated index labels, and `.at[label]`
        writes to every row that carries one. That silently moved four SM
        properties in Pasay onto Ortigas coordinates: same label, last write
        wins, no error. attach must address rows, not labels."""
        import pandas as pd

        monkeypatch.setattr(geocode, "load", lambda: {
            "ortigas:x": {"lat": 14.60, "lon": 121.04, "source": "osm", "precision": "exact"},
        })
        carried = pd.DataFrame({
            "chain": ["sm"], "mall_id": ["moa"],
            "lat": [14.53], "lon": [120.98],
            "geo_source": ["operator"], "geo_precision": ["exact"],
        })
        fresh = pd.DataFrame({
            "chain": ["ortigas"], "mall_id": ["x"],
            "lat": [None], "lon": [None],
            "geo_source": [None], "geo_precision": [None],
        })
        frame = pd.concat([carried, fresh])
        assert not frame.index.is_unique          # the condition that triggered it

        placed, _ = geocode.attach(frame)
        sm = placed[placed.chain == "sm"].iloc[0]
        ortigas = placed[placed.chain == "ortigas"].iloc[0]
        assert (sm.lat, sm.lon) == (14.53, 120.98)      # operator coordinates kept
        assert sm.geo_source == "operator"
        assert (ortigas.lat, ortigas.lon) == (14.60, 121.04)


class TestNominatimQueries:
    """Two defects in the Nominatim tier, both found by reading what the
    service actually returned rather than what the code assumed it would."""

    # The real three answers to "WalterMart San Jose, Philippines". Only the
    # last is the San Jose branch; the other two sit in a barangay of that name.
    SAN_JOSE_HITS: ClassVar[list] = [
        {
            "name": "WalterMart", "place_rank": 30, "lat": "15.3270548", "lon": "120.6450405",
            "osm_type": "way", "osm_id": 598237277, "display_name": "WalterMart, Concepcion, Tarlac",
            "address": {"road": "L. Cortez Street", "quarter": "San Jose", "suburb": "San Francisco",
                        "village": "Alfonso", "town": "Concepcion", "state": "Tarlac"},
        },
        {
            "name": "WalterMart", "place_rank": 30, "lat": "14.6714724", "lon": "120.5230916",
            "osm_type": "way", "osm_id": 2, "display_name": "WalterMart, Balanga, Bataan",
            "address": {"road": "Roman Superhighway", "suburb": "San Jose",
                        "village": "Bagong Silang", "city": "Balanga", "state": "Bataan"},
        },
        {
            "name": "WalterMart", "place_rank": 30, "lat": "15.7977778", "lon": "120.9937167",
            "osm_type": "way", "osm_id": 3, "display_name": "WalterMart, San Jose, Nueva Ecija",
            "address": {"road": "Maharlika Highway", "village": "Santo Niño 1st",
                        "city": "San Jose", "state": "Nueva Ecija"},
        },
    ]

    class FakeFetcher:
        """Answers one query and records every query it was asked."""

        def __init__(self, answers):
            self.answers = answers
            self.asked: list[str] = []

        def get_json(self, url, params=None):
            self.asked.append(params["q"])
            return self.answers.get(params["q"], [])

    def test_a_branch_is_placed_in_its_own_town_not_a_barangay_of_that_name(self):
        """Nominatim ranked a WalterMart in barangay San Jose, Concepcion above
        the one in San Jose, Nueva Ecija. Taking the first result that agreed
        with a region as broad as north-luzon put two distinct branches on one
        coordinate, and the map merged them into a bubble reading "2".

        Where the name runs out, the address has to take over: a match on the
        town outranks a match on a barangay or a street."""
        fetcher = self.FakeFetcher({"WalterMart San Jose, Philippines": self.SAN_JOSE_HITS})
        entry, reason = geocode.geocode_one(fetcher, "WalterMart San Jose", None, "north-luzon")
        assert reason == ""
        assert entry["ref"] == "way/3"
        assert (entry["lat"], entry["lon"]) == (15.797778, 120.993717)

    def test_a_name_the_address_cannot_explain_is_still_placed(self):
        """The counterweight: WalterMart Macapagal is tagged W.Mall and sits in
        Pasay, so neither the venue name nor the town carries "Macapagal". The
        street does, and a street is enough. Ranking must not become a filter."""
        hit = {
            "name": "W.Mall", "place_rank": 30, "lat": "14.532443", "lon": "120.988702",
            "osm_type": "way", "osm_id": 661740634, "display_name": "W.Mall, Pasay",
            "address": {"road": "President Diosdado Macapagal Boulevard", "city": "Pasay",
                        "region": "Metro Manila"},
        }
        fetcher = self.FakeFetcher({"WalterMart Macapagal, Philippines": [hit]})
        entry, reason = geocode.geocode_one(fetcher, "WalterMart Macapagal", None, "metro-manila")
        assert reason == ""
        assert entry["ref"] == "way/661740634"

    def test_the_country_is_never_named_twice(self):
        """Scraped addresses often end in "Philippines" already, and Nominatim
        answers a query naming the country twice with nothing at all. That
        silently disabled the whole address fallback: every coarser attempt for
        an SM property asked a question that could not be answered."""
        fetcher = self.FakeFetcher({})
        geocode.geocode_one(
            fetcher, "SM City CDO Uptown",
            "Gran Via St., Uptown Carmen, Cagayan de Oro, Misamis Oriental, Philippines",
            "mindanao",
        )
        assert fetcher.asked, "no query was issued"
        for query in fetcher.asked:
            assert not query.lower().endswith("philippines, philippines"), query
            assert query.lower().endswith("philippines"), query

    def test_the_ladder_reaches_the_town_but_never_the_country(self):
        """The coarse end of the ladder is the end that resolves. Asking only
        the three most specific tails of a long address meant the town was
        never asked for: every rung failed and the property went unplaced,
        while "1300 Pasay City, Philippines" would have answered.

        The last rung is the country itself, which answers with the centroid of
        the archipelago. That one must not be asked at all."""
        address = ("Coral Way cor., J.W. Diokno Blvd., Mall of Asia Complex, "
                   "Brgy. 076 Zone 10, CBP 1-A, 1300 Pasay City, Philippines")
        tails = geocode.address_tails(address)
        assert any("Pasay City" in t and "CBP" not in t for t in tails), tails
        assert all(geocode.normalize_name(t) != "philippines" for t in tails), tails

    def test_a_country_sized_answer_is_not_a_location(self):
        """Nominatim answers "Philippines" with the whole country at place_rank
        4. It is inside the bounding box and it agrees with any region, so
        nothing else in the chain would have stopped it."""
        country = {
            "name": "Philippines", "place_rank": 4, "lat": "12.7503486", "lon": "122.7312101",
            "osm_type": "relation", "osm_id": 443174, "display_name": "Philippines", "address": {},
        }
        fetcher = self.FakeFetcher({"Some Unknown Mall, Philippines": [country]})
        entry, reason = geocode.geocode_one(fetcher, "Some Unknown Mall", None, None)
        assert entry is None, entry
        assert reason

    def test_a_malformed_rank_skips_the_hit_rather_than_the_run(self):
        """Every candidate's place_rank is read now, not just the chosen one, so
        a hit carrying null or "" there took the whole refresh down with it -
        and a refresh saves at the end, so everything already resolved went with
        it. One unusable hit is worth one skipped hit."""
        good = {
            "name": "SM City Bacoor", "place_rank": 30, "lat": "14.4452", "lon": "120.9504",
            "osm_type": "way", "osm_id": 1, "display_name": "SM City Bacoor", "address": {},
        }
        for broken in (None, "", "thirty", {}):
            hits = [dict(good, place_rank=broken, osm_id=99), good]
            fetcher = self.FakeFetcher({"SM City Bacoor, Philippines": hits})
            entry, _ = geocode.geocode_one(fetcher, "SM City Bacoor", None, None)
            assert entry is not None, f"place_rank={broken!r} lost a usable hit"
            assert entry["ref"] == "way/1", f"place_rank={broken!r} chose the malformed hit"

    def test_a_name_with_nothing_distinctive_corroborates_nothing(self):
        """place_match reads an empty leftover as "the venue name accounted for
        all of it". That is true for "SM City" inside "SM City Cebu" and false
        for a property whose name is empty or entirely generic: there was never
        anything to account for, so it must not score as the strongest evidence
        available."""
        hit = {"name": "WalterMart", "address": {"city": "Pasay"}}
        assert geocode.place_match("", hit) == 0
        assert geocode.place_match("The Mall", hit) == 0            # all generic words
        assert geocode.place_match("SM City", {"name": "SM City Cebu", "address": {}}) == 2

    def test_a_property_with_nothing_to_search_is_not_searched(self):
        """Without a name the only query left was ", Philippines"."""
        fetcher = self.FakeFetcher({})
        entry, reason = geocode.geocode_one(fetcher, "", None, "metro-manila")
        assert entry is None
        assert fetcher.asked == [], fetcher.asked
        assert reason

    def test_a_malformed_coordinate_skips_the_hit_rather_than_the_run(self):
        """The same lesson as place_rank, one line earlier. `float(hit["lat"])`
        runs before any validation, so a hit whose lat is absent or not a number
        ended the run and discarded every property resolved before it."""
        good = {
            "name": "SM City Bacoor", "place_rank": 30, "lat": "14.4452", "lon": "120.9504",
            "osm_type": "way", "osm_id": 1, "display_name": "SM City Bacoor", "address": {},
        }
        broken = [
            dict(good, lat="not-a-number", osm_id=91),
            dict(good, lat=None, osm_id=92),
            {k: v for k, v in good.items() if k != "lat"} | {"osm_id": 93},
            dict(good, lon="", osm_id=94),
        ]
        for bad in broken:
            fetcher = self.FakeFetcher({"SM City Bacoor, Philippines": [bad, good]})
            entry, _ = geocode.geocode_one(fetcher, "SM City Bacoor", None, None)
            assert entry is not None, f"{bad.get('lat')!r}/{bad.get('lon')!r} lost a usable hit"
            assert entry["ref"] == "way/1", f"{bad.get('lat')!r} chose the malformed hit"


class TestPinVerification:
    """Four properties were drawn in the wrong place, and each one got there a
    different way. The tests are named for what let it happen, not for the
    property, because the property is only the example."""

    class FakeFetcher:
        """Answers searches by query and reverse lookups by coordinate."""

        def __init__(self, answers, reverse=None):
            self.answers = answers
            self.reverse = reverse or {}
            self.asked: list[str] = []

        def get_json(self, url, params=None):
            if "q" in params:
                self.asked.append(params["q"])
                return self.answers.get(params["q"], [])
            key = (params["lat"], params["lon"])
            self.asked.append(f"reverse {key[0]},{key[1]}")
            return self.reverse.get(key, {"error": "Unable to geocode"})

    # Robinsons Starmills is in San Fernando, Pampanga. Robinsons Gapan is in
    # Gapan, Nueva Ecija, 40 km away. Both are "north-luzon".
    STARMILLS: ClassVar[dict] = {
        "name": "Robinsons Starmills", "place_rank": 24,
        "lat": "15.048633", "lon": "120.698432",
        "osm_type": "relation", "osm_id": 8202540,
        "display_name": "Robinsons Starmills, San Fernando, Pampanga",
        "address": {"road": "Jose Abad Santos Avenue", "village": "San Jose",
                    "city": "San Fernando", "state": "Pampanga"},
    }

    def test_being_in_the_right_region_is_not_evidence(self):
        """A region is a quarter of the country. Robinsons Starmills matched
        nothing about Robinsons Gapan except that both are in north-luzon, and
        that was enough to record it as an exact pin 40 km from the property.

        The rest of the name has to turn up somewhere in the answer."""
        fetcher = self.FakeFetcher({"Robinsons Gapan, Philippines": [self.STARMILLS]})
        entry, reason = geocode.geocode_one(fetcher, "Robinsons Gapan", None, "north-luzon")
        assert entry is None, entry
        assert reason

    def test_a_town_match_stands_without_the_region_box(self):
        """The counterweight, and a real loss caused by the rule above being
        applied too hard: WalterMart Balanga is in Bataan, which the coarse
        latitude boxes put outside north-luzon. The hit names Balanga in its
        own address, which is better evidence than the box that disagrees."""
        hit = {
            "name": "WalterMart", "place_rank": 30,
            "lat": "14.6714724", "lon": "120.5230916",
            "osm_type": "way", "osm_id": 1330499494,
            "display_name": "WalterMart, Balanga, Bataan",
            "address": {"road": "Roman Superhighway", "city": "Balanga", "state": "Bataan"},
        }
        assert geocode.region_agrees("north-luzon", 14.6714724, 120.5230916) is False
        fetcher = self.FakeFetcher({"WalterMart Balanga, Philippines": [hit]})
        entry, reason = geocode.geocode_one(fetcher, "WalterMart Balanga", None, "north-luzon")
        assert reason == ""
        assert entry["ref"] == "way/1330499494"

    def test_a_pin_in_a_city_the_address_never_mentions_is_refused(self):
        """"The Strip" matched an OSM node called "The Strip Mall" in Quezon
        City, for a property whose own address says Capitol Commons, Pasig. The
        names agree and both are in Metro Manila, so only asking what is at the
        coordinate can tell them apart - and the ladder has to carry on to the
        next rung rather than stop at the first name that matched."""
        wrong = {
            "name": "The Strip Mall", "place_rank": 30,
            "lat": "14.601129", "lon": "121.088168",
            "osm_type": "node", "osm_id": 6006851691,
            "display_name": "The Strip Mall, Quezon City",
            "address": {"shop": "The Strip Mall", "quarter": "Bagumbayan", "city": "Quezon City"},
        }
        right = {
            "name": "Capitol Commons", "place_rank": 25,
            "lat": "14.5759371", "lon": "121.0635035",
            "osm_type": "relation", "osm_id": 12530292,
            "display_name": "Capitol Commons, Oranbo, Pasig",
            "address": {"quarter": "Oranbo", "city": "Pasig"},
        }
        fetcher = self.FakeFetcher(
            answers={
                "The Strip, Capitol Commons, Pasig City, Philippines": [wrong],
                "Capitol Commons, Pasig City, Philippines": [right],
            },
            reverse={
                ("14.601129", "121.088168"): {
                    "name": "The Strip Mall",
                    "address": {"shop": "The Strip Mall", "quarter": "Bagumbayan",
                                "city": "Quezon City", "country": "Philippines"},
                },
                ("14.575937", "121.063503"): {
                    "name": "Capitol Commons",
                    "address": {"quarter": "Oranbo", "city": "Pasig", "country": "Philippines"},
                },
            },
        )
        entry, reason = geocode.geocode_one(
            fetcher, "The Strip", "Capitol Commons, Pasig City", "metro-manila"
        )
        assert reason == ""
        assert entry["ref"] == "relation/12530292"

    def test_a_shared_filler_word_is_not_agreement(self):
        """"Pasig City" and "Quezon City" share a word. That word is what the
        first version of this check accepted as corroboration."""
        quezon = {"name": "", "address": {"city": "Quezon City", "quarter": "Bagumbayan"}}
        assert not geocode.supported("The Strip, Capitol Commons, Pasig City", quezon)
        pasig = {"name": "", "address": {"city": "Pasig", "quarter": "Oranbo"}}
        assert geocode.supported("The Strip, Capitol Commons, Pasig City", pasig)

    def test_verification_cannot_read_the_matched_name_back(self):
        """Reverse-geocoding the coordinate we just chose returns the feature we
        chose it from, and Nominatim repeats that feature's name inside the
        address breakdown as well, under a key named for its class. Reading
        either one back makes every pin corroborate itself."""
        hit = {"name": "The Strip Mall",
               "address": {"shop": "The Strip Mall", "city": "Quezon City"}}
        assert "strip" in geocode.hit_tokens(hit)
        assert "strip" not in geocode.hit_tokens(hit, place_only=True)

    def test_a_reverse_answer_without_a_usable_address_is_not_dry_land(self):
        """Two shapes that are not an address breakdown: one that would have
        raised on `.get`, and one with the key missing entirely. Neither says
        where this is, and neither may be read as saying it."""
        for body in ({"name": "Capitol Commons", "address": "Pasig"},
                     {"place_id": 1, "display_name": "Pasig"},
                     {"address": {}}):
            fetcher = self.FakeFetcher({}, reverse={("14.575937", "121.063503"): body})
            assert geocode.reverse_hit(fetcher, 14.575937, 121.063503) is None

    def test_a_saint_two_towns_share_is_not_a_town_they_share(self):
        """"San Jose del Monte, Bulacan" and "San Fernando, Pampanga" have two
        words in common and no place in common."""
        fernando = {"name": "", "address": {"city": "San Fernando", "state": "Pampanga"}}
        assert not geocode.supported("San Jose del Monte, Bulacan", fernando, place_only=True)
        monte = {"name": "", "address": {"city": "San Jose del Monte", "state": "Bulacan"}}
        assert geocode.supported("San Jose del Monte, Bulacan", monte, place_only=True)

    def test_a_property_whose_whole_name_is_a_filler_word_still_matches(self):
        """The counterweight to the two rules above: a barangay really is
        called Zone, and a mall really is called The Block. Filtering must not
        leave a correct pin with nothing to match on."""
        hit = {"name": "", "address": {"town": "Zone", "state": "Zamboanga del Sur"}}
        assert geocode.supported("Zone", hit, place_only=True)

    def test_verification_never_reads_the_property_name(self):
        """A brand name turns up in villages all over the country. Only the
        address may corroborate a pin."""
        fetcher = self.FakeFetcher({}, reverse={
            ("14.112709", "120.258804"): {
                "name": "", "address": {"village": "Ayala", "city": "Makati"},
            },
        })
        assert geocode.disagrees(fetcher, "Tagaytay City, Cavite", 14.112709, 120.258804)

    def test_the_check_itself_refuses_to_read_the_feature_name(self):
        """`hit_tokens(place_only=True)` is only worth what its caller passes.
        With the flag off, reverse-geocoding the coordinate returns the very
        node the match came from - and its name appears twice, once as `name`
        and once inside the address under its class key - so the pin
        corroborates itself and a Quezon City node keeps a Pasig property."""
        fetcher = self.FakeFetcher({}, reverse={
            ("14.601129", "121.088168"): {
                "name": "The Strip Mall",
                "address": {"shop": "The Strip Mall", "quarter": "Bagumbayan",
                            "city": "Quezon City", "country": "Philippines"},
            },
        })
        complaint = geocode.disagrees(
            fetcher, "The Strip, Capitol Commons, Pasig City", 14.601129, 121.088168
        )
        assert complaint and "Quezon City" in complaint, complaint

    def test_the_real_fetcher_actually_bypasses_its_cache(self):
        """The retry is only a retry if it reaches the network. Exercised
        against the real Fetcher, because a fake that reports it bypassed
        proves nothing about the one the scrapers use."""
        import tempfile

        from mallscape_scrape.fetch import Fetcher

        class Fake(Fetcher):
            def __init__(self, cache_dir):
                super().__init__(cache_dir, rate=1000.0)
                self.served = 0

            def _request(self, url, params):
                self.served += 1
                return f"body {self.served}"

        with tempfile.TemporaryDirectory() as tmp:
            f = Fake(tmp)
            assert f.get_text("https://example.test/x") == "body 1"
            assert f.get_text("https://example.test/x") == "body 1", "second read is cached"
            assert f.served == 1
            with f.bypass_cache():
                assert f.get_text("https://example.test/x") == "body 2", "bypass must refetch"
            assert f.served == 2
            assert f.get_text("https://example.test/x") == "body 2", \
                "the refetched body replaces the cached one"
            assert f.served == 2
            f.close()

    def test_a_pin_with_nothing_at_it_is_reported(self):
        """Nominatim answers a reverse lookup in open water with an error rather
        than a place, which is the whole of the sea test."""
        fetcher = self.FakeFetcher({}, reverse={})
        assert geocode.reverse_hit(fetcher, 14.112709, 120.258804) is None
        assert geocode.disagrees(
            fetcher, "Tagaytay City, Cavite", 14.112709, 120.258804
        ) == "nothing is at that coordinate"

    def test_an_operator_coordinate_is_overridden_only_in_writing(self, tmp_path, monkeypatch):
        """Operator coordinates outrank everything, which is right until an
        operator publishes a longitude 0.7 degrees off its own address. The
        registry may override one, but only with the reason recorded."""
        import pandas as pd

        registry = tmp_path / "coords.json"
        monkeypatch.setattr(geocode, "REGISTRY", registry)
        malls = pd.DataFrame([
            {"chain": "ayala", "mall_id": "ayala-serin", "mall_name": "Ayala Malls Serin",
             "lat": 14.112709, "lon": 120.258804, "geo_source": "operator",
             "geo_precision": "exact"},
            {"chain": "ayala", "mall_id": "ayala-other", "mall_name": "Other",
             "lat": 14.5, "lon": 121.0, "geo_source": "operator", "geo_precision": "exact"},
        ])

        geocode.save({"ayala:ayala-serin": {
            "lat": 14.112935, "lon": 120.958891, "source": "osm", "precision": "exact",
            "matched": "Ayala Malls Serin", "ref": "way/444842219",
        }})
        kept, _ = geocode.attach(malls)
        assert kept.loc[0, "lon"] == 120.258804, "an entry without a reason must not win"

        geocode.save({"ayala:ayala-serin": {
            "lat": 14.112935, "lon": 120.958891, "source": "osm", "precision": "exact",
            "matched": "Ayala Malls Serin", "ref": "way/444842219",
            "corrects_operator": "the published longitude is in the West Philippine Sea",
        }})
        fixed, _ = geocode.attach(malls)
        assert (fixed.loc[0, "lat"], fixed.loc[0, "lon"]) == (14.112935, 120.958891)
        assert fixed.loc[0, "geo_source"] == "osm"
        assert fixed.loc[0, "geo_precision"] == "exact"
        assert (fixed.loc[1, "lat"], fixed.loc[1, "lon"]) == (14.5, 121.0), \
            "every other operator coordinate is untouched"

        # An override whose coordinates are not numbers would otherwise replace
        # a good operator pin with NaN, still labelled osm/exact.
        geocode.save({"ayala:ayala-serin": {
            "lat": "not-a-number", "lon": 120.958891, "source": "osm",
            "precision": "exact", "matched": "", "ref": "way/1",
            "corrects_operator": "malformed",
        }})
        refused, missing = geocode.attach(malls)
        assert (refused.loc[0, "lat"], refused.loc[0, "lon"]) == (14.112709, 120.258804)
        assert refused.loc[0, "geo_source"] == "operator"
        assert missing == [], "an operator-placed row is never reported as unplaced"


class TestEmptyAndThin:
    """A mall that lists no tenants is either an operator gap or our bug, and
    the run report used to print both kinds in one undifferentiated list."""

    @staticmethod
    def _frames():
        import pandas as pd

        malls = pd.DataFrame(
            [{"chain": "sm", "mall_id": f"sm-{i}", "mall_name": f"SM {i}",
              "property_type": "mall"} for i in range(6)]
            + [{"chain": "sm", "mall_id": "sky-ranch", "mall_name": "Sky Ranch",
                "property_type": "amusement-park"}]
        )
        rows = []
        for i, n in enumerate([100, 110, 120, 130, 5, 0]):
            rows += [{"chain": "sm", "mall_id": f"sm-{i}", "store_name_raw": str(j)}
                     for j in range(n)]
        return malls, pd.DataFrame(rows)

    def test_an_empty_mall_is_separated_from_an_empty_amusement_park(self):
        """One of them is a hole in the data and one of them is a car park with
        rides. Listing them together is how nine zero-tenant malls sat in a
        footnote for a month."""
        malls, stores = self._frames()
        text = "\n".join(validate.empty_section(malls, stores, {("sm", "sm-5")}))
        assert "NOT ACCOUNTED FOR" in text
        assert "sm:sm-5" in text and "confirmed empty against the live site" in text
        assert "sky-ranch" in text and "which is expected" in text

    def test_an_accounted_for_empty_mall_is_not_reported_as_a_defect(self, monkeypatch, tmp_path):
        """The other half of the same rule. An empty mall with the evidence on
        file is a fact about the operator; one without is a bug in here, and
        the report has to say which is which or the list gets ignored."""
        registry = tmp_path / "empty.json"
        registry.write_text(json.dumps({"entries": {"sm:sm-5": {
            "name": "SM 5", "evidence": "the operator's own page 404s", "checked": "2026-08-30",
        }}}))
        monkeypatch.setattr(validate, "EMPTY_DIRECTORIES", registry)
        malls, stores = self._frames()
        text = "\n".join(validate.empty_section(malls, stores, {("sm", "sm-5")}))
        assert "NOT ACCOUNTED FOR" not in text
        assert "the operator's own page 404s" in text

    def test_an_entry_that_stopped_applying_is_named_for_deletion(self, monkeypatch, tmp_path):
        """SM City La Union published no tenants in July and 199 in August. An
        exemption nobody removes is a licence for the next real defect."""
        registry = tmp_path / "empty.json"
        registry.write_text(json.dumps({"entries": {"sm:sm-0": {
            "name": "SM 0", "evidence": "was empty once", "checked": "2026-07-26",
        }}}))
        monkeypatch.setattr(validate, "EMPTY_DIRECTORIES", registry)
        malls, stores = self._frames()
        text = "\n".join(validate.empty_section(malls, stores, set()))
        assert "no longer apply" in text and "sm:sm-0" in text

    def test_a_mall_far_under_its_chain_median_is_named(self):
        """SM City East Ortigas serving 139 of its own reported 153 tenants is
        within range. A mall serving 5 where its chain's median is 110 is not,
        and nobody should have to notice that by eye."""
        malls, stores = self._frames()
        text = "\n".join(validate.thin_section(malls, stores))
        assert "sm:sm-4: 5 tenants" in text
        assert "sm:sm-0" not in text

    def test_an_empty_directory_is_re_asked_before_it_is_believed(self):
        """A cached body cannot tell "this mall has no directory" apart from
        "this request failed". SM City La Union returned zero tenants during
        the July scrape and 201 when asked again, so the retry has to reach
        past the cache before an empty mall is recorded as a fact."""
        from mallscape_core.models import Mall, Store
        from mallscape_scrape.scrapers.base import MallChainScraper

        class FakeFetcher:
            def __init__(self):
                self.bypassed = False

            @contextlib.contextmanager
            def bypass_cache(self):
                self.bypassed = True
                yield self

        class Flaky(MallChainScraper):
            chain = "sm"

            def discover_malls(self):
                return [Mall(chain="sm", mall_id="sm-la-union", mall_name="SM City La Union")]

            def scrape_mall(self, mall):
                if not self.fetcher.bypassed:
                    return []
                return [Store(chain="sm", mall_id=mall.mall_id, store_name_raw="Watsons")]

        scraper = Flaky(FakeFetcher())
        _, stores = scraper.scrape_all()
        assert len(stores) == 1
        assert scraper.confirmed_empty == []
        assert any("live site served 1" in w for w in scraper.warnings), scraper.warnings

    def test_a_mall_still_empty_on_the_live_site_is_recorded_as_such(self):
        """The other half: WalterMart Silang really does publish "No store
        available", and saying so is different from saying nothing."""
        from mallscape_core.models import Mall
        from mallscape_scrape.scrapers.base import MallChainScraper

        class FakeFetcher:
            @contextlib.contextmanager
            def bypass_cache(self):
                yield self

        class Empty(MallChainScraper):
            chain = "waltermart"

            def discover_malls(self):
                return [Mall(chain="waltermart", mall_id="silang", mall_name="WalterMart Silang")]

            def scrape_mall(self, mall):
                return []

        scraper = Empty(FakeFetcher())
        scraper.scrape_all()
        assert scraper.confirmed_empty == ["silang"]

    def test_a_failed_request_is_never_recorded_as_an_empty_mall(self):
        """A mall whose fetch raised has told us nothing about its tenants."""
        from mallscape_core.models import Mall
        from mallscape_scrape.scrapers.base import MallChainScraper

        class FakeFetcher:
            @contextlib.contextmanager
            def bypass_cache(self):
                yield self

        class Broken(MallChainScraper):
            chain = "sm"

            def discover_malls(self):
                return [Mall(chain="sm", mall_id="sm-x", mall_name="SM X")]

            def scrape_mall(self, mall):
                raise TimeoutError("upstream timed out")

        scraper = Broken(FakeFetcher())
        scraper.scrape_all()
        assert scraper.confirmed_empty == []
        assert any("FAILED sm-x" in w for w in scraper.warnings)

    def test_a_retry_that_raises_is_not_an_empty_mall_either(self):
        """The half that is easy to get wrong: the cached read said nothing and
        the live retry never answered. Two non-answers are not a zero."""
        from mallscape_core.models import Mall
        from mallscape_scrape.scrapers.base import MallChainScraper

        class FakeFetcher:
            def __init__(self):
                self.bypassed = False

            @contextlib.contextmanager
            def bypass_cache(self):
                self.bypassed = True
                yield self

        class Flaky(MallChainScraper):
            chain = "sm"

            def discover_malls(self):
                return [Mall(chain="sm", mall_id="sm-y", mall_name="SM Y")]

            def scrape_mall(self, mall):
                if self.fetcher.bypassed:
                    raise TimeoutError("upstream timed out")
                return []

        scraper = Flaky(FakeFetcher())
        scraper.scrape_all()
        assert scraper.confirmed_empty == []

    def test_a_chain_with_an_even_number_of_malls_uses_a_real_median(self):
        """Counts of 10, 20, 100 and 110 have a median of 60, so the quarter
        line is 15 and only the 10 is thin. Taking the upper middle value put
        the line at 25 and named a normal mall."""
        import pandas as pd

        malls = pd.DataFrame([
            {"chain": "x", "mall_id": f"x-{i}", "mall_name": f"X {i}", "property_type": "mall"}
            for i in range(4)
        ])
        rows = []
        for i, n in enumerate([10, 20, 100, 110]):
            rows += [{"chain": "x", "mall_id": f"x-{i}", "store_name_raw": str(j)}
                     for j in range(n)]
        text = "\n".join(validate.thin_section(malls, pd.DataFrame(rows)))
        assert "x:x-0" in text
        assert "x:x-1" not in text, "20 against a median of 60 is not thin"

    def test_the_report_survives_a_frame_with_no_property_type(self):
        """The column is not in every frame this has to read, and a report that
        raises is a report nobody gets."""
        import pandas as pd

        malls = pd.DataFrame([{"chain": "x", "mall_id": "x-1", "mall_name": "X"}])
        stores = pd.DataFrame(columns=["chain", "mall_id", "store_name_raw"])
        text = "\n".join(validate.empty_section(malls, stores, set()))
        assert "NOT ACCOUNTED FOR" in text, text
        assert validate.thin_section(malls, stores)
