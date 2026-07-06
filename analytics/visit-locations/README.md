# Visit Locations Analytics (Evidence.dev)

An [Evidence.dev](https://evidence.dev) project for reviewing and verifying the
2023 clustered visit-location data.

## Pages

- `/` — verification table of all 93 locations (sortable, searchable) with
  groupings, first/last visit date & time, visit rates, a bubble map, group
  rollups, and data-quality checks.
- `/locations/<cluster_id>` — drill-down per location: total visits, first and
  last visit (date · time), active span, average visits per week, average days
  between visits, map, rank, and the other members of its group.
- `/groups/<group_id>` — drill-down per cluster group (`-1` = unclustered).

## Running locally

```bash
cd analytics/visit-locations
npm install
npm run sources   # loads sources/visits/locations.csv into DuckDB
npm run dev       # http://localhost:3000
```

`npm run build` produces a static site in `build/`.

## Merging into an existing Evidence instance

Copy these into your instance and re-run `npm run sources`:

- `sources/visits/` (the CSV + `connection.yaml`)
- `pages/index.md` (rename to e.g. `pages/visit-locations.md` if you already
  have an index), `pages/locations/`, and `pages/groups/`

No extra dependencies are required beyond the standard `@evidence-dev/csv`
datasource plugin.

## Porting data from another analysis or report

The map and this project's source CSV are both producible by the reusable
`viz.geo_map` tool (`tools/geo_map.py`) — callable by an agent (Agno tool), a
workflow (registry capability `viz.geo_map`), or a user (CLI). It accepts a
file path, in-memory records, or raw CSV text, and a column `mapping` so data
from other analyses ports in without editing the source.

Expected schema (template: `tools/geo_map_template.csv`, JSON Schema:
`tools/geo_map_schema.json`): required `lat`, `lng`; optional `id`, `label`,
`weight`, `group`, `first_seen`, `last_seen`. Unknown extra columns are carried
into popups verbatim.

```bash
# standalone HTML map + an Evidence source CSV for this project, from any dataset
python -m tools.geo_map \
  --input some_other_report.csv \
  --map lat=latitude --map lng=longitude --map weight=hit_count --map group=category \
  --title "My dataset" --weight-label hits \
  --out my_map.html \
  --evidence-source-out analytics/visit-locations/sources/visits/locations.csv
# then: cd analytics/visit-locations && npm run sources && npm run dev
```

From Python / an agent:

```python
from tools.geo_map import build_geo_map
build_geo_map(records=rows, mapping={"lat": "latitude", "lng": "longitude"},
              out_html="map.html")
```

## Data

`sources/visits/locations.csv` is the clustered 2023 export
(`visit_locations_2023_clustered.csv`) enriched with:

- `address` — reverse-geocoded from each cluster's coordinates via
  OpenStreetMap Nominatim
- `first_date` / `first_time` / `last_date` / `last_time` — split from the
  original timestamps for easy display and filtering
- `group_label` — human-readable form of the `cluster` column
  (`-1` → "Unclustered")

The clustered export does **not** contain individual visit timestamps — only
first-seen, last-seen, and a count per location. Drop the raw pre-clustering
visits file into `sources/visits/` to enable true per-visit drill-downs.
