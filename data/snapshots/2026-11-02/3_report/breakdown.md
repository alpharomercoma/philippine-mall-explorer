# Mall directory scrape - breakdown (2026-11-02)

**306 properties · 42,313 listings · 10 chains**

Generated deterministically from the snapshot in `data/snapshots/2026-11-02/`. Regenerate with `mallscape report --date 2026-11-02`.

## Data quality

4,113 of 42,313 listings have no confidently mapped category.
522 normalized brand keys have multiple raw variants or require review.
Raw listings are retained; these signals describe uncertainty rather than removing rows.

### Locations

306 of 306 properties have a coordinate.

| source    | properties |
|-----------|-----------:|
| nominatim |         91 |
| operator  |         58 |
| osm       |        157 |

| precision | properties |
|-----------|-----------:|
| address   |         22 |
| exact     |        260 |
| locality  |         24 |

## Chains

| chain      | properties |   malls |   listings | fetched    | source                                      | method                               |
|------------|-----------:|--------:|-----------:|------------|---------------------------------------------|--------------------------------------|
| araneta    |          4 |       4 |        755 | 2026-11-02 | aranetacity.com                             | server-rendered HTML                 |
| ayala      |         32 |      32 |      5,974 | 2026-11-02 | api.ayalamalls.com                          | explore-v2 JSON API                  |
| filinvest  |          5 |       5 |        953 | 2026-11-02 | filinvestlifemalls.com                      | server-rendered HTML table           |
| fishermall |          2 |       2 |        342 | 2026-11-02 | fishermall.com.ph                           | loadlevel.php HTML fragments         |
| megaworld  |         28 |      28 |      2,125 | 2026-11-02 | megaworld-lifestylemalls.com                | Contentstack headless CMS API        |
| ortigas    |          4 |       4 |      1,303 | 2026-11-02 | ortigasmalls.com                            | Laravel/Inertia data-page JSON       |
| robinsons  |         54 |      54 |      8,583 | 2026-11-02 | robinsonsmalls.com + vmd.robinsonsmalls.com | Drupal HTML + Google Sites fallback  |
| sm         |        126 |      95 |     19,779 | 2026-11-02 | smsupermalls.com                            | JSON API (list-of-malls + tenants)   |
| starmall   |          4 |       4 |        279 | 2026-11-02 | starmalls.com.ph                            | Elementor JSON-escaped blob          |
| waltermart |         47 |      47 |      2,220 | 2026-11-02 | malls.waltermart.com.ph                     | store index + per-store branches API |
| **total**  |    **306** | **275** | **42,313** |            |                                             |                                      |

`properties` counts everything the operator publishes a directory for; `malls` excludes non-mall retail (supermarkets, condo podiums, amusement parks, office annexes). **Use `malls` for chain-vs-chain comparison.**

### Accuracy caveats

- **ayala** - Ayala's API returns duplicate `(mall, merchant)` pairs with distinct ids but no distinguishing fields, so listing counts run above the number of unique brands present.

## Properties

### araneta (4 properties, 755 listings)

| property       | region       | type | listings |
|----------------|--------------|------|---------:|
| Farmers Plaza  | metro-manila | mall |      205 |
| Ali Mall       | metro-manila | mall |      199 |
| Gateway Mall 1 | metro-manila | mall |      193 |
| Gateway Mall 2 | metro-manila | mall |      158 |

### ayala (32 properties, 5,974 listings)

| property                    | region       | type | listings |
|-----------------------------|--------------|------|---------:|
| Market! Market!             | metro-manila | mall |      492 |
| Ayala Center Cebu           | visayas      | mall |      417 |
| Glorietta                   | metro-manila | mall |      410 |
| Trinoma                     | metro-manila | mall |      389 |
| Ayala Malls Manila Bay      | metro-manila | mall |      368 |
| Abreeza                     | mindanao     | mall |      297 |
| Ayala Malls Capitol Central | visayas      | mall |      271 |
| U. P. Town Center           | metro-manila | mall |      253 |
| MarQuee Mall                | north-luzon  | mall |      251 |
| Ayala Malls Feliz           | metro-manila | mall |      237 |
| Greenbelt                   | metro-manila | mall |      229 |
| Centrio Mall                | mindanao     | mall |      215 |
| Ayala Malls Nuvali          | south-luzon  | mall |      214 |
| Ayala Malls Circuit         | metro-manila | mall |      190 |
| Fairview Terraces           | metro-manila | mall |      179 |
| Ayala Malls Central Bloc    | visayas      | mall |      167 |
| One Ayala                   | metro-manila | mall |      154 |
| Ayala Malls Vertis North    | metro-manila | mall |      152 |
| Ayala Malls Cloverleaf      | metro-manila | mall |      125 |
| Harbor Point                | north-luzon  | mall |      115 |
| Ayala Malls Serin           | south-luzon  | mall |      106 |
| Ayala Malls The 30th        | metro-manila | mall |       98 |
| Ayala Malls Vermosa         | south-luzon  | mall |       90 |
| Ayala Malls Marikina        | metro-manila | mall |       88 |
| The District Imus           | south-luzon  | mall |       79 |
| Ayala Malls Legazpi         | south-luzon  | mall |       77 |
| Bonifacio High Street       | metro-manila | mall |       76 |
| Pavilion Mall               | south-luzon  | mall |       65 |
| Metro Point Mall            | metro-manila | mall |       50 |
| One Bonifacio High Street   | metro-manila | mall |       45 |
| The District Dasmarinas     | south-luzon  | mall |       41 |
| Shops at Serendra           | metro-manila | mall |       34 |

### filinvest (5 properties, 953 listings)

| property                  | region       | type | listings |
|---------------------------|--------------|------|---------:|
| Festival Mall             | metro-manila | mall |      784 |
| Fora Mall                 | south-luzon  | mall |       65 |
| Main Square               | south-luzon  | mall |       58 |
| Filinvest Malls Dumaguete | visayas      | mall |       27 |
| IL Corso                  | visayas      | mall |       19 |

### fishermall (2 properties, 342 listings)

| property                  | region       | type | listings |
|---------------------------|--------------|------|---------:|
| Fisher Mall Quezon Avenue | metro-manila | mall |      195 |
| Fisher Mall Malabon       | metro-manila | mall |      147 |

### megaworld (28 properties, 2,125 listings)

| property                          | region       | type | listings |
|-----------------------------------|--------------|------|---------:|
| Venice Grand Canal Mall           | metro-manila | mall |      305 |
| Uptown Mall                       | metro-manila | mall |      248 |
| Lucky Chinatown Mall              | metro-manila | mall |      194 |
| Eastwood Mall                     | metro-manila | mall |      184 |
| Festive Walk Mall                 | visayas      | mall |      155 |
| Newport City                      | metro-manila | mall |      150 |
| Southwoods Mall                   | south-luzon  | mall |      142 |
| Eastwood City Walk                | metro-manila | mall |       91 |
| Forbes Town                       | metro-manila | mall |       75 |
| Lucky Chinatown - Prosperity Wing | metro-manila | mall |       56 |
| San Lorenzo Place Mall            | metro-manila | mall |       53 |
| Eastwood Cyber Mall               | metro-manila | mall |       51 |
| Festive Walk Parade               | visayas      | mall |       44 |
| California Garden Square          | metro-manila | mall |       43 |
| Mactan Newtown                    | visayas      | mall |       42 |
| Uptown Parade                     | metro-manila | mall |       39 |
| McKinley West                     | metro-manila | mall |       38 |
| Lucky Chinatown - Imperial Wing   | metro-manila | mall |       37 |
| Paseo Center                      | metro-manila | mall |       34 |
| Alabang West Parade               | metro-manila | mall |       33 |
| Arcovia City                      | metro-manila | mall |       28 |
| The Greenhouse at Village Square  | metro-manila | mall |       28 |
| Twin Lakes                        | south-luzon  | mall |       17 |
| Three Central Mall                | metro-manila | mall |       15 |
| The Clubhouse at Temple Drive     | metro-manila | mall |       14 |
| Boracay Newcoast                  | visayas      | mall |        9 |
| The Shoppes at McKinley West      | metro-manila | mall |        0 |
| Tuscany at McKinley Hill          | metro-manila | mall |        0 |

### ortigas (4 properties, 1,303 listings)

| property    | region       | type | listings |
|-------------|--------------|------|---------:|
| Greenhills  | metro-manila | mall |      921 |
| Estancia    | metro-manila | mall |      307 |
| Tiendesitas | metro-manila | mall |       39 |
| The Strip   | metro-manila | mall |       36 |

### robinsons (54 properties, 8,583 listings)

| property                      | region       | type | listings |
|-------------------------------|--------------|------|---------:|
| Robinsons Place Manila        | metro-manila | mall |      672 |
| Robinsons Magnolia            | metro-manila | mall |      425 |
| Robinsons Galleria            | metro-manila | mall |      399 |
| Robinsons Place Antipolo      | metro-manila | mall |      306 |
| Robinsons Place Dumaguete     | visayas      | mall |      259 |
| Robinsons Place Tacloban      | visayas      | mall |      248 |
| Robinsons Novaliches          | metro-manila | mall |      242 |
| Robinsons Galleria South      | south-luzon  | mall |      234 |
| Robinsons Place Ilocos        | north-luzon  | mall |      233 |
| Robinsons Place Malolos       | north-luzon  | mall |      233 |
| Robinsons Place Iligan        | mindanao     | mall |      225 |
| Robinsons Galleria Cebu       | visayas      | mall |      222 |
| Robinsons Place Dasmarinas    | south-luzon  | mall |      209 |
| Robinsons Metro East          | metro-manila | mall |      206 |
| Robinsons Place Imus          | south-luzon  | mall |      205 |
| Robinsons Place Santiago      | north-luzon  | mall |      199 |
| Robinsons Place Tuguegarao    | north-luzon  | mall |      199 |
| Robinsons Place Palawan       | south-luzon  | mall |      193 |
| Robinsons Place Iloilo        | visayas      | mall |      189 |
| Robinsons Place Lipa          | south-luzon  | mall |      182 |
| Robinsons Place Naga          | south-luzon  | mall |      174 |
| Robinsons Place Gen. Trias    | south-luzon  | mall |      172 |
| Robinsons Gapan               | north-luzon  | mall |      159 |
| Robinsons Pagadian            | mindanao     | mall |      149 |
| Robinsons Starmills           | north-luzon  | mall |      149 |
| Robinsons Place Valencia      | mindanao     | mall |      144 |
| Robinsons Place Pangasinan    | north-luzon  | mall |      143 |
| Robinsons Place Butuan        | mindanao     | mall |      142 |
| Robinsons Place La Union      | north-luzon  | mall |      127 |
| Opus Mall                     | metro-manila | mall |      125 |
| Robinsons Place Ormoc         | visayas      | mall |      124 |
| Robinsons North Tacloban      | visayas      | mall |      113 |
| Robinsons Cybergate Cebu      | visayas      | mall |      112 |
| Robinsons Place Jaro          | visayas      | mall |      111 |
| Robinsons Place Las Pinas     | metro-manila | mall |      111 |
| Robinsons Place Tagum         | mindanao     | mall |      111 |
| Robinsons Place Pavia         | visayas      | mall |      104 |
| Robinsons Place Roxas         | visayas      | mall |      104 |
| Robinsons Place Bacolod       | visayas      | mall |      103 |
| Robinsons Sta. Rosa           | south-luzon  | mall |       98 |
| Robinsons Place Antique       | visayas      | mall |       92 |
| Robinsons Town Mall Malabon   | metro-manila | mall |       86 |
| Robinsons Fuente              | visayas      | mall |       80 |
| Robinsons Place GenSan        | mindanao     | mall |       79 |
| Robinsons Cainta              | metro-manila | mall |       62 |
| Robinsons Angeles             | north-luzon  | mall |       61 |
| Robinsons Otis                | metro-manila | mall |       61 |
| Robinsons Town Mall Los Banos | south-luzon  | mall |       53 |
| Robinsons Cagayan de Oro      | mindanao     | mall |       45 |
| Robinsons Luisita             | north-luzon  | mall |       33 |
| Robinsons Tagaytay            | south-luzon  | mall |       33 |
| Robinsons Cybergate Davao     | mindanao     | mall |       24 |
| The Plaza Bagong Silang       | metro-manila | mall |       19 |
| Robinsons Cybergate Bacolod   | visayas      | mall |        0 |

### sm (126 properties, 19,779 listings)

| property                      | region       | type               | listings |
|-------------------------------|--------------|--------------------|---------:|
| SM City North Edsa            | metro-manila | mall               |      868 |
| SM City Fairview              | metro-manila | mall               |      739 |
| SM Megamall                   | metro-manila | mall               |      692 |
| SM Mall of Asia               | metro-manila | mall               |      686 |
| SM City Santa Rosa            | south-luzon  | mall               |      537 |
| SM City Pampanga              | north-luzon  | mall               |      515 |
| SM City Cebu                  | visayas      | mall               |      497 |
| SM City Clark                 | north-luzon  | mall               |      434 |
| SM Seaside City Cebu          | visayas      | mall               |      377 |
| SM City Dasmariñas            | south-luzon  | mall               |      361 |
| SM City Davao                 | mindanao     | mall               |      361 |
| SM City Baguio                | north-luzon  | mall               |      354 |
| SM City Iloilo                | visayas      | mall               |      352 |
| SM Southmall                  | metro-manila | mall               |      345 |
| SM City Bacolod               | visayas      | mall               |      330 |
| SM City Manila                | metro-manila | mall               |      302 |
| SM City Sucat                 | metro-manila | mall               |      298 |
| SM City Bicutan               | metro-manila | mall               |      290 |
| SM City San Lazaro            | metro-manila | mall               |      290 |
| SM City Bacoor                | south-luzon  | mall               |      276 |
| SM City Lipa                  | south-luzon  | mall               |      262 |
| SM City Cabanatuan            | north-luzon  | mall               |      259 |
| SM Lanang                     | mindanao     | mall               |      257 |
| SM City Marilao               | north-luzon  | mall               |      242 |
| SM City Batangas              | south-luzon  | mall               |      236 |
| SM CDO Downtown Premier       | mindanao     | mall               |      229 |
| SM City Baliwag               | north-luzon  | mall               |      228 |
| SM City Calamba               | south-luzon  | mall               |      228 |
| SM City Grand Central         | metro-manila | mall               |      226 |
| SM City Lucena                | south-luzon  | mall               |      220 |
| SM City Legazpi               | south-luzon  | mall               |      207 |
| SM City La Union              | north-luzon  | mall               |      199 |
| SM Aura                       | metro-manila | mall               |      195 |
| SM City Sta. Mesa             | metro-manila | mall               |      191 |
| SM City General Santos        | mindanao     | mall               |      188 |
| SM City Tanza                 | south-luzon  | mall               |      187 |
| SM City Tuguegarao            | north-luzon  | mall               |      187 |
| SM City Marikina              | metro-manila | mall               |      180 |
| SM City Olongapo Central      | north-luzon  | mall               |      180 |
| SM City Molino                | south-luzon  | mall               |      179 |
| SM City Naga                  | south-luzon  | mall               |      172 |
| SM City Trece Martires        | south-luzon  | mall               |      172 |
| SM City Urdaneta Central      | north-luzon  | mall               |      172 |
| SM City Rosales               | north-luzon  | mall               |      171 |
| SM City San Pablo             | south-luzon  | mall               |      166 |
| SM City San Jose Del Monte    | north-luzon  | mall               |      163 |
| SM City Taytay                | metro-manila | mall               |      161 |
| The Podium                    | metro-manila | mall               |      161 |
| SM City Caloocan              | metro-manila | mall               |      160 |
| SM City Consolacion           | visayas      | mall               |      160 |
| SM City Novaliches            | metro-manila | mall               |      158 |
| SM City Cauayan               | north-luzon  | mall               |      157 |
| SM City Sorsogon              | south-luzon  | mall               |      156 |
| SM City Butuan                | mindanao     | mall               |      152 |
| SM City Tarlac                | north-luzon  | mall               |      152 |
| SM City Valenzuela            | metro-manila | mall               |      146 |
| SM City Bataan                | north-luzon  | mall               |      145 |
| SM City Masinag               | metro-manila | mall               |      145 |
| SM City San Mateo             | metro-manila | mall               |      145 |
| SM City Laoag                 | north-luzon  | mall               |      144 |
| SM City Sto. Tomas            | south-luzon  | mall               |      144 |
| SM City CDO Uptown            | mindanao     | mall               |      140 |
| SM City East Ortigas          | metro-manila | mall               |      139 |
| SM City Puerto Princesa       | south-luzon  | mall               |      137 |
| SM Center Lemery              | south-luzon  | mall               |      132 |
| SM City Mindpro               | mindanao     | mall               |      128 |
| SM City Telabastagan          | north-luzon  | mall               |      127 |
| SM City Roxas                 | visayas      | mall               |      122 |
| SM Center Dagupan             | north-luzon  | mall               |      114 |
| SM City Daet                  | south-luzon  | mall               |      114 |
| SM City Rosario               | south-luzon  | mall               |      113 |
| SM City BF Parañaque          | metro-manila | mall               |      110 |
| SM J Mall                     | visayas      | mall               |      108 |
| SM Center Pulilan             | north-luzon  | mall               |      107 |
| SM Center Angono              | metro-manila | mall               |      102 |
| SM Center Ormoc               | visayas      | mall               |      101 |
| SM Center Las Piñas           | metro-manila | mall               |      100 |
| SM Center Tuguegarao Downtown | north-luzon  | mall               |      100 |
| S Maison                      | metro-manila | mall               |       99 |
| SM Center Pasig               | metro-manila | mall               |       91 |
| SM Center San Pedro           | south-luzon  | mall               |       86 |
| SM Center Muntinlupa          | metro-manila | mall               |       74 |
| SM Center Sangandaan          | north-luzon  | mall               |       68 |
| SM Center Imus                | south-luzon  | mall               |       67 |
| SM Megacenter Cabanatuan      | north-luzon  | mall               |       61 |
| SM City Olongapo Downtown     | north-luzon  | mall               |       56 |
| SM City San Fernando Downtown | north-luzon  | mall               |       56 |
| SMDC Light Mall               | metro-manila | residential-retail |       46 |
| SM Savemore Tacloban          | visayas      | supermarket        |       40 |
| SM By the Bay                 | metro-manila | mall               |       39 |
| SM Center Antipolo Downtown   | metro-manila | mall               |       38 |
| SM Center Shaw                | metro-manila | mall               |       37 |
| SMDC Jazz Mall                | metro-manila | residential-retail |       37 |
| MOA Square                    | metro-manila | mall               |       30 |
| SMDC Mplace Mall              | metro-manila | residential-retail |       28 |
| SM Center Congressional       | metro-manila | mall               |       25 |
| SMDC Strip at Mezza           | metro-manila | residential-retail |       25 |
| SMDC Sun Mall                 | metro-manila | residential-retail |       24 |
| SM Savemore Apalit            | north-luzon  | supermarket        |       23 |
| SMDC Air Mall                 | metro-manila | residential-retail |       23 |
| SMDC Fame Mall                | metro-manila | residential-retail |       23 |
| SMDC Grace Mall               | metro-manila | residential-retail |       23 |
| SM Savemore Nagtahan          | metro-manila | supermarket        |       21 |
| SM Hypermarket Sucat Lopez    | metro-manila | supermarket        |       16 |
| SM Marketmall Dasmarinas      | south-luzon  | mall               |       16 |
| SMDC Strip at Sea             | metro-manila | residential-retail |       15 |
| SMDC Strip at Shore           | metro-manila | residential-retail |       15 |
| SMDC Strip at Grass           | metro-manila | residential-retail |       14 |
| SM Hypermarket Lapu-Lapu      | visayas      | supermarket        |       13 |
| SMDC Breeze Mall              | metro-manila | residential-retail |       11 |
| NU MALL OF ASIA BUILDING      | metro-manila | office-annex       |        9 |
| Wind Residences               | south-luzon  | residential-retail |        8 |
| Mall Of Asia Arena Annex Bldg | metro-manila | office-annex       |        7 |
| SMDC Strip at Trees           | metro-manila | residential-retail |        7 |
| SMDC Green Mall               | metro-manila | residential-retail |        6 |
| SMDC Strip at Blue            | metro-manila | residential-retail |        5 |
| SMDC Strip at Shell           | metro-manila | residential-retail |        5 |
| SMDC Strip at Princeton       | metro-manila | residential-retail |        4 |
| SMDC Strip at Berkeley        | metro-manila | residential-retail |        2 |
| SMDC Strip at Shine           | metro-manila | residential-retail |        2 |
| Sky Ranch Baguio              | north-luzon  | amusement-park     |        1 |
| Sky Ranch Pampanga            | north-luzon  | amusement-park     |        1 |
| Sky Ranch Tagaytay            | south-luzon  | amusement-park     |        1 |
| SMBY Amusement Park           | nan          | amusement-park     |        1 |
| SM City Zamboanga             | mindanao     | mall               |        0 |
| SM Makati                     | metro-manila | mall               |        0 |

### starmall (4 properties, 279 listings)

| property                    | region       | type | listings |
|-----------------------------|--------------|------|---------:|
| Starmall Alabang            | metro-manila | mall |      107 |
| Starmall San Jose del Monte | north-luzon  | mall |       98 |
| Starmall EDSA-Shaw          | metro-manila | mall |       64 |
| Starmall Talisay Cebu       | visayas      | mall |       10 |

### waltermart (47 properties, 2,220 listings)

| property                     | region       | type | listings |
|------------------------------|--------------|------|---------:|
| WalterMart North EDSA        | metro-manila | mall |      117 |
| WalterMart Makati            | metro-manila | mall |      105 |
| WalterMart Dasmariñas        | south-luzon  | mall |       83 |
| WalterMart Antipolo          | metro-manila | mall |       77 |
| WalterMart Gapan             | north-luzon  | mall |       77 |
| WalterMart Sucat             | metro-manila | mall |       76 |
| WalterMart Bacoor            | south-luzon  | mall |       75 |
| WalterMart Sta. Maria        | north-luzon  | mall |       75 |
| WalterMart E.Rodriguez       | metro-manila | mall |       72 |
| WalterMart Bicutan           | metro-manila | mall |       69 |
| WalterMart Guiguinto         | north-luzon  | mall |       66 |
| WalterMart Sta. Rosa         | south-luzon  | mall |       60 |
| WalterMart San Fernando      | north-luzon  | mall |       59 |
| WalterMart Baliwag           | north-luzon  | mall |       57 |
| WalterMart Taytay            | metro-manila | mall |       57 |
| WalterMart Balayan           | south-luzon  | mall |       56 |
| WalterMart Naic              | south-luzon  | mall |       55 |
| WalterMart Subic             | north-luzon  | mall |       55 |
| WalterMart Malolos           | north-luzon  | mall |       54 |
| WalterMart General Trias     | south-luzon  | mall |       53 |
| WalterMart Arayat            | north-luzon  | mall |       51 |
| WalterMart Cabanatuan        | north-luzon  | mall |       49 |
| WalterMart Makiling          | south-luzon  | mall |       49 |
| WalterMart Paniqui           | north-luzon  | mall |       49 |
| WalterMart Plaridel          | north-luzon  | mall |       49 |
| WalterMart Balanga           | north-luzon  | mall |       48 |
| WalterMart Nasugbu           | south-luzon  | mall |       47 |
| WalterMart Tanauan           | south-luzon  | mall |       47 |
| WalterMart Caloocan          | metro-manila | mall |       46 |
| WalterMart Trece Martires    | south-luzon  | mall |       45 |
| WalterMart Concepcion        | north-luzon  | mall |       42 |
| WalterMart W.MALL Muntinlupa | metro-manila | mall |       39 |
| WalterMart W.MALL Macapagal  | metro-manila | mall |       38 |
| WalterMart San Jose          | north-luzon  | mall |       38 |
| WalterMart Candelaria        | south-luzon  | mall |       31 |
| WalterMart Cabuyao           | south-luzon  | mall |       28 |
| WalterMart Capas             | north-luzon  | mall |       27 |
| WalterMart The Junction      | metro-manila | mall |       23 |
| WalterMart Batangas City     | south-luzon  | mall |       22 |
| WalterMart Carmona           | south-luzon  | mall |       21 |
| WalterMart Sta. Rosa Bel-Air | south-luzon  | mall |       17 |
| WalterMart Talavera          | north-luzon  | mall |       15 |
| WalterMart Altaraza          | nan          | mall |        1 |
| WalterMart Mabalacat         | north-luzon  | mall |        0 |
| WalterMart San Pascual       | south-luzon  | mall |        0 |
| WalterMart Silang            | south-luzon  | mall |        0 |
| WalterMart San Rafael        | north-luzon  | mall |        0 |

## Properties with zero listings

9 properties publish no tenant directory. Every one was checked against its source and is an upstream gap, not a parse failure.

| chain      | property                     | id                           |
|------------|------------------------------|------------------------------|
| megaworld  | The Shoppes at McKinley West | the-shoppes-at-mckinley-west |
| megaworld  | Tuscany at McKinley Hill     | tuscany-at-mckinley-hill     |
| robinsons  | Robinsons Cybergate Bacolod  | cybergate-bacolod            |
| sm         | SM City Zamboanga            | sm-city-zamboanga            |
| sm         | SM Makati                    | sm-makati                    |
| waltermart | WalterMart Mabalacat         | mabalacat                    |
| waltermart | WalterMart San Pascual       | san-pascual                  |
| waltermart | WalterMart Silang            | silang                       |
| waltermart | WalterMart San Rafael        | waltermart-san-rafael        |

## Excluded operators

Operators investigated but not scraped. Each entry records the finding and what would have to change for a scraper to become viable.

| operator                            | malls | status                     |
|-------------------------------------|------:|----------------------------|
| CityMall (DoubleDragon)             |    43 | no-tenant-directory        |
| Gaisano Capital Group               |     - | blocked-not-verified       |
| Gaisano Grand Malls                 |    46 | no-tenant-directory        |
| LCC Group (Bicol)                   |     - | blocked-not-verified       |
| LTS Malls                           |     - | not-located                |
| NCCC Malls                          |     9 | likely-no-tenant-directory |
| Primark Town Centers (LKY Group)    |    45 | no-tenant-directory        |
| Puregold Price Club                 |     - | out-of-scope-shape         |
| Shangri-La Plaza (Shang Properties) |     1 | no-current-directory       |
| Vista Malls (Vista Land)            |    20 | no-tenant-directory        |
| XentroMalls                         |    19 | removed-unreliable-source  |

**CityMall (DoubleDragon)** - citymall.com.ph is a thin DoubleDragon corporate shell; /citymall_map returns a 423-byte stub. DoubleDragon reported 43 operating CityMalls at end-2024 with a target of 100 by 2030. These are small community malls anchored by a supermarket; no per-mall tenant directory is published on any official domain found.

**Gaisano Capital Group** - NOT VERIFIED. Site returns HTTP 403 to scripted requests. Whether a tenant directory exists behind it is unknown.

**Gaisano Grand Malls** - VERIFIED. WordPress; branches are ordinary posts (slug gaisano-grand-mall-<place>) reachable via /wp-json/wp/v2/posts and a paginated /branches/ listing. Each branch post contains only ADDRESS, MALL HOURS (supermarket + department store) and PHONE NUMBER - no tenant list. These are department-store/supermarket-anchored retail centres, not tenant-leased malls.

**LCC Group (Bicol)** - NOT VERIFIED. Serves a 4.6KB 'Redirecting...' bot-challenge shell to scripted requests (same WAF pattern as XentroMall's parked domain and Shangri-La's).

**LTS Malls** - NOT VERIFIED. No official domain located; ltsmalls.com does not resolve. Search results conflate it with NCCC. Operator identity needs confirming before scraping.

**NCCC Malls** - PARTIALLY VERIFIED. nccc.com.ph/business-unit/nccc-malls/ is a corporate business-unit page (company profile, vision/mission, press) with no tenant listing found. ~9 branches across Davao, Tagum and Palawan per their own copy. No per-mall directory URL located.

**Primark Town Centers (LKY Group)** - ~45 provincial community centers exposed as WordPress pages named location-<place> (plus location-luzon-malls / -visayas-malls / -mindanao-malls index pages). Each page carries only a street address and leasing contact - no tenant list. Mall list IS obtainable from the WP REST API.

**Puregold Price Club** - NOT a mall operator in this dataset's sense: each Puregold branch is a single supermarket/hypermarket, not a leased mall with a tenant roster. Adding ~400 branches would inject 400 'malls' each holding one 'tenant' (itself) and would badly skew brand-presence and mall-size analysis. /store-locator/ 404s; the correct locator path was not found before running out of budget.

**Shangri-La Plaza (Shang Properties)** - Their official domain shangrila-plaza.com no longer resolves (no DNS), and shangrilaplaza.com.ph is a ParkLogic parked page offering the domain for sale. The only surviving official store listing is a Google Sites page at sites.google.com/view/shangcommunity/store-listing, which is explicitly stamped 'Updated as of February 02, 2021' - COVID-era data, five years stale. NOT scraped: importing 2021 tenants into a 2026 snapshot would silently corrupt month-over-month brand analysis.

**Vista Malls (Vista Land)** - WordPress site with a page per mall and a /stores/<slug>/ route, but the store sections render only logo carousels - no tenant names in the markup. The dev mirror (dev.vistamalls.com.ph/<mall>/store/) still contains Lorem ipsum placeholders, so the directory was never populated. Mall list IS obtainable from the WP REST API (/wp-json/wp/v2/pages).

**XentroMalls** - Scraped and then removed on 2026-07-27. Four of the 19 mall pages (montalban-town-center, tanay-town-center, xentro-mall-calapan, xentro-mall-lemery) list two tenants per line with no delimiter, e.g. <li>Jollibee Auto Sonix Watch Store</li>. Verified at byte level: no inner markup, no non-breaking space, no repeated space. No cleaner source exists - wp-json returns an empty content.rendered because the content lives in page-builder post meta, /wp/v2/pages/<id>/revisions is 401, and a browser trace shows no XHR for the tenant list. Separately, 16 of 19 pages were last modified 2019-02-11, so the directories are years stale.

## Known gaps inside scraped chains

### araneta

| property                        | region       | opened | type               |
|---------------------------------|--------------|--------|--------------------|
| Coliseum Circle                 | metro-manila | -      | arena-retail       |
| Cyberpark Tower 1               | metro-manila | -      | office-retail      |
| Cyberpark Tower 2               | metro-manila | -      | office-retail      |
| Cyberpark Tower 3               | metro-manila | -      | office-retail      |
| Farmers Market                  | metro-manila | -      | public-market      |
| Fiesta Carnival                 | metro-manila | -      | arcade-retail      |
| Gateway Courtyard               | metro-manila | -      | open-air-retail    |
| Gateway Tower                   | metro-manila | -      | office-retail      |
| Manhattan Heights               | metro-manila | -      | residential-retail |
| Manhattan Parkview              | metro-manila | -      | residential-retail |
| Manhattan Parkway               | metro-manila | -      | residential-retail |
| Manhattan Plaza                 | metro-manila | -      | residential-retail |
| New Frontier Theater            | metro-manila | -      | arcade-retail      |
| Novotel Manila Araneta City     | metro-manila | -      | hotel-retail       |
| ibis Styles Manila Araneta City | metro-manila | -      | hotel-retail       |

### ayala

| property                         | region       | opened     | type            |
|----------------------------------|--------------|------------|-----------------|
| Ayala Malls Arca South           | metro-manila | 2026-02-13 | mall            |
| Ayala Malls Evo City             | south-luzon  | 2025-09-05 | mall            |
| Ayala Malls Gatewalk             | visayas      | 2026-12-16 | mall            |
| Ayala Malls Parklinks            | metro-manila | -          | mall            |
| Azuela High Street               | mindanao     | 2024-10    | lifestyle-strip |
| Garden Bloc at Cebu IT Park      | visayas      | 2015       | lifestyle-strip |
| Seagrove                         | visayas      | 2024-01    | lifestyle-strip |
| Shops at Ayala North Exchange    | metro-manila | 2019-12    | lifestyle-strip |
| The District North Point         | visayas      | 2013-04-03 | mall            |
| The Link Car Park                | metro-manila | 2010       | carpark-retail  |
| The Shops Ayala Triangle Gardens | metro-manila | 2022       | lifestyle-strip |
| The Shops at Atria               | visayas      | 2015       | lifestyle-strip |
| The Shops at Azuela Cove         | mindanao     | 2021       | lifestyle-strip |
| The Walk at Cebu IT Park         | visayas      | 2008       | lifestyle-strip |

### megaworld

| property             | region      | opened | type |
|----------------------|-------------|--------|------|
| Clark Cityfront Mall | north-luzon | -      | mall |

### ortigas

| property  | region       | opened | type           |
|-----------|--------------|--------|----------------|
| Industria | metro-manila | -      | community-mall |

### robinsons

| property                           | region       | opened | type           |
|------------------------------------|--------------|--------|----------------|
| Robinsons Bulacan Town Center      | north-luzon  | 2027   | mall           |
| Robinsons Townville BF Paranaque   | metro-manila | -      | community-mall |
| Robinsons Townville Buhay na Tubig | south-luzon  | -      | community-mall |
| Robinsons Townville Cabanatuan     | north-luzon  | 2008   | community-mall |
| Robinsons Townville Meycauayan     | north-luzon  | -      | community-mall |
| Robinsons Townville Perdices       | visayas      | -      | community-mall |
| Robinsons Townville Pulilan        | north-luzon  | 2010   | community-mall |
| Robinsons Townville Regalado       | metro-manila | -      | community-mall |
| The Jewel                          | metro-manila | 2027   | mall           |
| The Mall @ NUSTAR                  | visayas      | 2022   | luxury-mall    |

### sm

| property        | region       | opened | type             |
|-----------------|--------------|--------|------------------|
| SM Araneta City | metro-manila | 1980   | mall             |
| SM Delgado      | visayas      | 1982   | department-store |
| SM Quiapo       | metro-manila | 1972   | department-store |

### starmall

| property                 | region       | opened | type           |
|--------------------------|--------------|--------|----------------|
| Starmall Annex Las Pinas | metro-manila | -      | community-mall |
| Starplaza Agro           | metro-manila | -      | community-mall |

## Brand reach

10,625 distinct brands after normalization.

| brand                  | malls | chains |
|------------------------|------:|-------:|
| POTATO CORNER          |   220 |     10 |
| WATSONS                |   216 |     10 |
| JOLLIBEE               |   182 |     10 |
| BENCH                  |   172 |     10 |
| SAMSUNG                |   172 |      8 |
| BANCO DE ORO           |   166 |      9 |
| PENSHOPPE              |   164 |     10 |
| EXECUTIVE OPTICAL      |   154 |     10 |
| KFC                    |   146 |      8 |
| VIVO                   |   143 |      9 |
| FAMOUS BELGIAN WAFFLES |   141 |      6 |
| MANG INASAL            |   139 |      9 |
| IAN DARCY              |   135 |      8 |
| KETTLE KORN            |   134 |      8 |
| NATIONAL BOOKSTORE     |   129 |      8 |
| GOLDILOCKS             |   128 |     10 |
| AFICIONADO             |   126 |      8 |
| DUNKIN                 |   125 |      6 |
| OPPO                   |   122 |      9 |
| CHOWKING               |   121 |      9 |
