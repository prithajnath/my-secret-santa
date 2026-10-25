# Reference data

## us_places.csv

US populated places used to approximate member locations on group maps (each
opted-in member is shown at their nearest place instead of their address).

- Source: GeoNames `cities15000` (https://download.geonames.org/export/dump/cities15000.zip)
- License: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), © GeoNames (https://www.geonames.org)
- Filter: country `US`, feature codes `PPL`, `PPLA`–`PPLA4`, `PPLC`, `PPLG` (city sections
  `PPLX` excluded), population >= 50,000, plus the largest place in each state so every
  state has at least one
- Columns: `geonameid, name, state, population, lat, lon`

Loaded into the `places` table by the `add places table` migration. To refresh, regenerate
the CSV with the same filter and add a new migration that reloads it.
