# mallscape run report - 2026-08-31

- **araneta**: 4 malls, 319 store rows
- **ayala**: 32 malls, 5984 store rows
- **filinvest**: 5 malls, 953 store rows
- **fishermall**: 2 malls, 342 store rows
- **megaworld**: 26 malls, 2101 store rows
- **ortigas**: 4 malls, 1282 store rows
- **robinsons**: 54 malls, 8464 store rows
- **sm**: 126 malls, 19843 store rows
- **starmall**: 4 malls, 279 store rows
- **waltermart**: 47 malls, 2220 store rows

## Properties with no tenants

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

- ⚠ 15 malls hold under 25% of their chain's median tenant count:
  - ayala:ayala-serendra: 34 tenants against a chain median of 159.5
  - ortigas:the-strip: 36 tenants against a chain median of 170
  - ortigas:tiendesitas: 39 tenants against a chain median of 170
  - robinsons:the-plaza: 19 tenants against a chain median of 142
  - robinsons:robinsons-cybergate-davao: 24 tenants against a chain median of 142
  - robinsons:robinsons-tagaytay: 32 tenants against a chain median of 142
  - robinsons:robinsons-luisita: 33 tenants against a chain median of 142
  - sm:sm-marketmall-dasmarinas: 16 tenants against a chain median of 161
  - sm:sm-cherry-congressional: 25 tenants against a chain median of 161
  - sm:moa-square: 30 tenants against a chain median of 161
  - sm:sm-cherry-shaw: 37 tenants against a chain median of 161
  - sm:sm-cherry-antipolo: 38 tenants against a chain median of 161
  - sm:sm-by-the-bay: 39 tenants against a chain median of 161
  - starmall:talisay: 10 tenants against a chain median of 81
  - waltermart:altaraza: 1 tenants against a chain median of 49

## Diff vs 2026-08-30
- no anomalous store-count drops

## Scraper warnings
- [sm] scrape failed entirely (HTTPStatusError: Client error '403 Forbidden' for url 'https://www.smsupermalls.com/list-of-malls?region=all&keyword=&page=0'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/403); expecting the previous snapshot's rows to be carried forward
- operating malls with no published directory - absent from store data by necessity: Robinsons Townville Pulilan (opened 2010); Robinsons Townville Cabanatuan (opened 2008); Robinsons Townville Meycauayan; Robinsons Townville Regalado; Robinsons Townville BF Paranaque; Robinsons Townville Buhay na Tubig; Robinsons Townville Perdices; The Mall @ NUSTAR (opened 2022)
- cybergate-bacolod: 0 stores, confirmed against the live site
- operating malls with no published directory - absent from store data by necessity: Ayala Malls Arca South (opened 2026-02-13); Ayala Malls Evo City (opened 2025-09-05); The District North Point (opened 2013-04-03); Ayala Malls Parklinks
- the-shoppes-at-mckinley-west: 0 stores, confirmed against the live site
- [waltermart] scrape failed entirely (HTTPStatusError: Client error '403 Forbidden' for url 'https://malls.waltermart.com.ph/malls/'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/403); expecting the previous snapshot's rows to be carried forward
- could not verify mall roster (HTTPStatusError)
- FAILED gateway-mall: HTTPStatusError: Client error '403 Forbidden' for url 'https://aranetacity.com/shopping/gateway-mall'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/403
- FAILED gateway-mall-2: HTTPStatusError: Client error '403 Forbidden' for url 'https://aranetacity.com/shopping/gateway-mall-2-shop'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/403
- FAILED ali-mall: HTTPStatusError: Client error '403 Forbidden' for url 'https://aranetacity.com/shopping/ali-mall'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/403
- FAILED farmers-plaza: HTTPStatusError: Client error '403 Forbidden' for url 'https://aranetacity.com/shopping/farmers-plaza'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/403
- [araneta] listings collapsed against the previous snapshot; carried that snapshot's rows forward instead (their `fetched` date says so)
- [sm] listings collapsed against the previous snapshot; carried that snapshot's rows forward instead (their `fetched` date says so)
- [waltermart] listings collapsed against the previous snapshot; carried that snapshot's rows forward instead (their `fetched` date says so)
