---
title: Data & provenance
---

Full transparency on where every number comes from. Three layers:

1. **Original export** — `visit_locations_2023_clustered.csv`, committed untouched
   at [`analytics/visit-locations/data/visit_locations_2023_clustered.original.csv`](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/main/analytics/visit-locations/data/visit_locations_2023_clustered.original.csv).
   Nine columns per row: `cluster_id`, `lat_med`, `lng_med`, `points`,
   `first_seen`, `last_seen`, `lat`, `lng`, `cluster`.
2. **Enrichment** — `address` (reverse-geocoded from `lat`/`lng` via OpenStreetMap
   Nominatim, one lookup per row) and `group_label` (readable form of `cluster`).
   Nothing from the original export was altered; timestamps were split into a
   naive local part plus their original UTC offset so they can be displayed
   exactly as recorded, with no timezone conversion anywhere.
3. **Derived metrics** — computed in the page queries, never stored:
   `active_days = last_seen date − first_seen date + 1`,
   `visits_per_week = points ÷ (active_days ÷ 7)`,
   `avg_days_between_visits = active_days ÷ points`.

## Complete dataset — every row, every column

The full working table, one row per location, timestamps verbatim. Use the
download button on the table to export it. Click a row for that location's
full-record view.

```sql everything
select
    '/locations/' || cluster_id::int as location_link,
    cluster_id::int as cluster_id,
    lat_med, lng_med,
    visits as points,
    strftime(first_seen, '%Y-%m-%d %H:%M:%S') || utc_offset_first as first_seen,
    strftime(last_seen, '%Y-%m-%d %H:%M:%S') || utc_offset_last   as last_seen,
    lat, lng,
    group_id as cluster,
    address,
    group_label
from visits.locations
order by cluster_id::int
```

<DataTable data={everything} search=true rows=all link=location_link wrapTitles=true>
    <Column id=cluster_id title="cluster_id" />
    <Column id=lat_med title="lat_med" fmt='0.00000000' />
    <Column id=lng_med title="lng_med" fmt='0.00000000' />
    <Column id=points title="points" />
    <Column id=first_seen title="first_seen (verbatim)" />
    <Column id=last_seen title="last_seen (verbatim)" />
    <Column id=lat title="lat" fmt='0.00000000' />
    <Column id=lng title="lng" fmt='0.00000000' />
    <Column id=cluster title="cluster" />
    <Column id=address title="address" wrap=true />
    <Column id=group_label title="group_label" />
</DataTable>

## Data dictionary

```sql dictionary
select * from (values
    ('cluster_id',  'Original export', 'integer', 'Cluster identifier assigned by the clustering run'),
    ('lat_med',     'Original export', 'double',  'Median latitude of the cluster''s member points'),
    ('lng_med',     'Original export', 'double',  'Median longitude of the cluster''s member points'),
    ('points',      'Original export', 'integer', 'Count of raw location fixes assigned to the cluster — shown as "visits" throughout'),
    ('first_seen',  'Original export', 'timestamp + offset', 'Earliest fix in the cluster, local time with UTC offset (-05:00 EST / -04:00 EDT)'),
    ('last_seen',   'Original export', 'timestamp + offset', 'Latest fix in the cluster, local time with UTC offset'),
    ('lat',         'Original export', 'double',  'Plotted latitude — identical to lat_med in this export'),
    ('lng',         'Original export', 'double',  'Plotted longitude — identical to lng_med in this export'),
    ('cluster',     'Original export', 'integer', 'Higher-level group assignment; -1 means unclustered / noise'),
    ('address',     'Enrichment',      'text',    'Reverse-geocoded from lat/lng via OSM Nominatim (zoom 18), one lookup per row'),
    ('group_label', 'Enrichment',      'text',    'Readable form of cluster: -1 → "Unclustered", n → "Group n"')
) as t(field, source, type, description)
```

<DataTable data={dictionary} rows=all>
    <Column id=field title="Field" />
    <Column id=source title="Source" />
    <Column id=type title="Type" />
    <Column id=description title="Description" wrap=true />
</DataTable>

## Known limits

- The clustered export contains **no individual visit timestamps** — only
  first-seen, last-seen, and a count per location. Every per-visit claim beyond
  those three values would be inference, so none is shown. Add the raw
  pre-clustering file as a second source to unlock per-visit drill-downs.
- Addresses are a best-effort nearest-address lookup at the cluster's median
  coordinate; the coordinate is the ground truth, the address is a convenience.
