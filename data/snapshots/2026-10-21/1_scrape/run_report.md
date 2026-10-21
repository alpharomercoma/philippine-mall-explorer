# mallscape run report - 2026-10-21

- **araneta**: 4 malls, 319 store rows
- **ayala**: 32 malls, 6063 store rows
- **filinvest**: 5 malls, 953 store rows
- **fishermall**: 2 malls, 342 store rows
- **megaworld**: 26 malls, 2124 store rows
- **ortigas**: 4 malls, 1300 store rows
- **robinsons**: 54 malls, 8576 store rows
- **sm**: 126 malls, 19791 store rows
- **starmall**: 4 malls, 279 store rows
- **waltermart**: 47 malls, 2220 store rows

## Properties with no tenants

- 7 mall(s) publish no directory, each on the record:
  - robinsons:cybergate-bacolod (Robinsons Cybergate Bacolod) - checked 2026-08-30: The mall-info page loads and is titled, but its directory container holds no store-name elements, and vmd.robinsonsmalls.com lists no Cybergate Bacolod page to fall back to. Recorded in robinsons_coverage.json as the one property with a page but no directory.
  - sm:sm-city-zamboanga (SM City Zamboanga) - checked 2026-08-30: The tenants API returns counts:0 for mallCode SMZA, and the public directory page /mall-directory/sm-city-zamboanga/shops/ answers 404.
  - sm:sm-makati (SM Makati) - checked 2026-08-30: The tenants API returns counts:0 for mallCode SMKT, and the public directory page /mall-directory/sm-makati/shops/ answers 404.
  - waltermart:mabalacat (WalterMart Mabalacat) - checked 2026-08-30: The mall page offers no category links, and all six category pages render the empty-state alert 'No store available.' with no tenant anchors.
  - waltermart:san-pascual (WalterMart San Pascual) - checked 2026-08-30: The mall page offers no category links, and all six category pages render the empty-state alert 'No store available.' with no tenant anchors.
  - waltermart:silang (WalterMart Silang) - checked 2026-08-30: The mall page offers no category links, and all six category pages render the empty-state alert 'No store available.' with no tenant anchors.
  - waltermart:waltermart-san-rafael (WalterMart San Rafael) - checked 2026-08-30: New to the mall list this run, replacing the delisted Pasay branch. Its category pages render 'No store available.' with no tenant anchors.
- 1 entr(ies) in empty_directories.json no longer apply and should be deleted: megaworld:the-shoppes-at-mckinley-west

## Suspiciously thin malls

- ⚠ 17 malls hold under 25% of their chain's median tenant count:
  - ayala:ayala-serendra: 34 tenants against a chain median of 167.5
  - ayala:ayala-the-district-dasmarinas: 41 tenants against a chain median of 167.5
  - megaworld:boracay-newcoast: 9 tenants against a chain median of 43
  - ortigas:the-strip: 36 tenants against a chain median of 172.5
  - ortigas:tiendesitas: 39 tenants against a chain median of 172.5
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

## Diff vs 2026-10-02
- ⚠ store-count drops >20% (possible redesign):
  - ('sm', 'sm-city-olongapo-downtown'): 71 → 56 (-21%)

## Scraper warnings
- sm-city-zamboanga: 0 stores, confirmed against the live site
- sm-makati: 0 stores, confirmed against the live site
- operating malls with no published directory - absent from store data by necessity: Robinsons Townville Pulilan (opened 2010); Robinsons Townville Cabanatuan (opened 2008); Robinsons Townville Meycauayan; Robinsons Townville Regalado; Robinsons Townville BF Paranaque; Robinsons Townville Buhay na Tubig; Robinsons Townville Perdices; The Mall @ NUSTAR (opened 2022)
- cybergate-bacolod: 0 stores, confirmed against the live site
- operating malls with no published directory - absent from store data by necessity: Ayala Malls Arca South (opened 2026-02-13); Ayala Malls Evo City (opened 2025-09-05); The District North Point (opened 2013-04-03); Ayala Malls Parklinks
- mall 'altaraza' exists only in the branches API - not on /malls/
- mabalacat: 0 stores, confirmed against the live site
- san-pascual: 0 stores, confirmed against the live site
- silang: 0 stores, confirmed against the live site
- waltermart-san-rafael: 0 stores, confirmed against the live site
- could not verify mall roster (HTTPError)
- FAILED gateway-mall: HTTPError: HTTP Error 404: 
- FAILED gateway-mall-2: HTTPError: HTTP Error 404: 
- FAILED ali-mall: HTTPError: HTTP Error 404: 
- FAILED farmers-plaza: HTTPError: HTTP Error 404: 
- [araneta] listings collapsed against the previous snapshot; carried that snapshot's rows forward instead (their `fetched` date says so)
