# mallscape run report - 2026-11-02

- **araneta**: 4 malls, 755 store rows
- **ayala**: 32 malls, 5974 store rows
- **filinvest**: 5 malls, 953 store rows
- **fishermall**: 2 malls, 342 store rows
- **megaworld**: 28 malls, 2125 store rows
- **ortigas**: 4 malls, 1303 store rows
- **robinsons**: 54 malls, 8583 store rows
- **sm**: 126 malls, 19779 store rows
- **starmall**: 4 malls, 279 store rows
- **waltermart**: 47 malls, 2220 store rows

## Properties with no tenants

- ⚠ 1 MALL(S) PUBLISHED NOTHING AND ARE NOT ACCOUNTED FOR. Investigate each one, then either fix the scraper or record the evidence in empty_directories.json:
  - megaworld:tuscany-at-mckinley-hill (Tuscany at McKinley Hill) - confirmed empty against the live site
- 8 mall(s) publish no directory, each on the record:
  - megaworld:the-shoppes-at-mckinley-west (The Shoppes at McKinley West) - checked 2026-08-30: Listed in Megaworld's mall feed as uid bltd1ea5541ca1324e8. All 2,101 entries of the chain-wide tenant feed were scanned and not one references that uid.
  - robinsons:cybergate-bacolod (Robinsons Cybergate Bacolod) - checked 2026-08-30: The mall-info page loads and is titled, but its directory container holds no store-name elements, and vmd.robinsonsmalls.com lists no Cybergate Bacolod page to fall back to. Recorded in robinsons_coverage.json as the one property with a page but no directory.
  - sm:sm-city-zamboanga (SM City Zamboanga) - checked 2026-08-30: The tenants API returns counts:0 for mallCode SMZA, and the public directory page /mall-directory/sm-city-zamboanga/shops/ answers 404.
  - sm:sm-makati (SM Makati) - checked 2026-08-30: The tenants API returns counts:0 for mallCode SMKT, and the public directory page /mall-directory/sm-makati/shops/ answers 404.
  - waltermart:mabalacat (WalterMart Mabalacat) - checked 2026-08-30: The mall page offers no category links, and all six category pages render the empty-state alert 'No store available.' with no tenant anchors.
  - waltermart:san-pascual (WalterMart San Pascual) - checked 2026-08-30: The mall page offers no category links, and all six category pages render the empty-state alert 'No store available.' with no tenant anchors.
  - waltermart:silang (WalterMart Silang) - checked 2026-08-30: The mall page offers no category links, and all six category pages render the empty-state alert 'No store available.' with no tenant anchors.
  - waltermart:waltermart-san-rafael (WalterMart San Rafael) - checked 2026-08-30: New to the mall list this run, replacing the delisted Pasay branch. Its category pages render 'No store available.' with no tenant anchors.

## Suspiciously thin malls

- ⚠ 16 malls hold under 25% of their chain's median tenant count:
  - ayala:ayala-serendra: 34 tenants against a chain median of 160.5
  - megaworld:boracay-newcoast: 9 tenants against a chain median of 43.5
  - ortigas:the-strip: 36 tenants against a chain median of 173
  - ortigas:tiendesitas: 39 tenants against a chain median of 173
  - robinsons:the-plaza: 19 tenants against a chain median of 143
  - robinsons:robinsons-cybergate-davao: 24 tenants against a chain median of 143
  - robinsons:robinsons-luisita: 33 tenants against a chain median of 143
  - robinsons:robinsons-tagaytay: 33 tenants against a chain median of 143
  - sm:sm-marketmall-dasmarinas: 16 tenants against a chain median of 161
  - sm:sm-cherry-congressional: 25 tenants against a chain median of 161
  - sm:moa-square: 30 tenants against a chain median of 161
  - sm:sm-cherry-shaw: 37 tenants against a chain median of 161
  - sm:sm-cherry-antipolo: 38 tenants against a chain median of 161
  - sm:sm-by-the-bay: 39 tenants against a chain median of 161
  - starmall:talisay: 10 tenants against a chain median of 81
  - waltermart:altaraza: 1 tenants against a chain median of 49

## Diff vs 2026-10-22
- malls added: ['the-shoppes-at-mckinley-west', 'tuscany-at-mckinley-hill']
- no anomalous store-count drops

## Scraper warnings
- sm-city-zamboanga: 0 stores, confirmed against the live site
- sm-makati: 0 stores, confirmed against the live site
- operating malls with no published directory - absent from store data by necessity: Robinsons Townville Pulilan (opened 2010); Robinsons Townville Cabanatuan (opened 2008); Robinsons Townville Meycauayan; Robinsons Townville Regalado; Robinsons Townville BF Paranaque; Robinsons Townville Buhay na Tubig; Robinsons Townville Perdices; The Mall @ NUSTAR (opened 2022)
- cybergate-bacolod: 0 stores, confirmed against the live site
- operating malls with no published directory - absent from store data by necessity: Ayala Malls Arca South (opened 2026-02-13); Ayala Malls Evo City (opened 2025-09-05); The District North Point (opened 2013-04-03); Ayala Malls Parklinks
- the-shoppes-at-mckinley-west: 0 stores, confirmed against the live site
- tuscany-at-mckinley-hill: 0 stores, confirmed against the live site
- mall 'altaraza' exists only in the branches API - not on /malls/
- mabalacat: 0 stores, confirmed against the live site
- san-pascual: 0 stores, confirmed against the live site
- silang: 0 stores, confirmed against the live site
- waltermart-san-rafael: 0 stores, confirmed against the live site
