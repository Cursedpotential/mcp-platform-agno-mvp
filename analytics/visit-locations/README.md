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
