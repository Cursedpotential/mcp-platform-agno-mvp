```sql location
select
    cluster_id::int as cluster_id,
    address,
    coalesce(nullif(trim(split_part(address, ',', 1) || ' ' || split_part(address, ',', 2)), ''), 'Unknown') as short_address,
    group_id::int as group_id,
    group_label,
    lat, lng, visits,
    strftime(first_seen, '%Y-%m-%d · %H:%M') as first_visit,
    strftime(last_seen, '%Y-%m-%d · %H:%M')  as last_visit,
    date_diff('day', first_seen::date, last_seen::date) + 1 as active_days,
    round(visits / ((date_diff('day', first_seen::date, last_seen::date) + 1) / 7.0), 2)   as visits_per_week,
    round(visits / ((date_diff('day', first_seen::date, last_seen::date) + 1) / 30.44), 1) as visits_per_month,
    round((date_diff('day', first_seen::date, last_seen::date) + 1) / visits::float, 1)    as avg_days_between_visits,
    'https://www.google.com/maps?q=' || lat || ',' || lng as gmaps_link
from visits.locations
where cluster_id::int = try_cast('${params.cluster_id}' as int)
```

# {location[0].short_address}

**{location[0].address}**
Cluster {params.cluster_id} · {location[0].group_label} · {location[0].lat}, {location[0].lng} · <a href={location[0].gmaps_link} target="_blank">open in Google Maps</a>

<BigValue data={location} value=visits fmt=num0 title="Total visits" />
<BigValue data={location} value=first_visit title="First visit" />
<BigValue data={location} value=last_visit title="Last visit" />
<BigValue data={location} value=active_days fmt=num0 title="Active span (days)" />
<BigValue data={location} value=visits_per_week fmt=num2 title="Avg visits / week" />
<BigValue data={location} value=avg_days_between_visits fmt=num1 title="Avg days between visits" />

<PointMap
    data={location}
    lat=lat
    long=lng
    pointName=short_address
    tooltipType=hover
    tooltip={[
        {id: 'address', showColumnName: false, valueClass: 'font-semibold'},
        {id: 'visits', title: 'Visits', fmt: 'num0'}
    ]}
/>

## Full record

Every field behind this data point — the original export columns verbatim
(timestamps shown exactly as recorded, including their original UTC offsets),
the enrichment fields added later, and the formula behind every derived number.
See [Data & provenance](/data) for the untouched source file.

```sql full_record
with r as (
    select * from visits.locations
    where cluster_id::int = try_cast('${params.cluster_id}' as int)
)
select 1 as ord, 'cluster_id' as field, cluster_id::int::varchar as value, 'Original export' as source, 'Cluster identifier from the clustering run' as notes from r
union all select 2, 'lat_med', lat_med::varchar, 'Original export', 'Median latitude of the cluster''s member points' from r
union all select 3, 'lng_med', lng_med::varchar, 'Original export', 'Median longitude of the cluster''s member points' from r
union all select 4, 'points', visits::int::varchar, 'Original export', 'Count of raw location fixes assigned to this cluster' from r
union all select 5, 'first_seen', strftime(first_seen, '%Y-%m-%d %H:%M:%S') || utc_offset_first, 'Original export', 'Verbatim, with original UTC offset' from r
union all select 6, 'last_seen', strftime(last_seen, '%Y-%m-%d %H:%M:%S') || utc_offset_last, 'Original export', 'Verbatim, with original UTC offset' from r
union all select 7, 'lat', lat::varchar, 'Original export', 'Plotted latitude (equals lat_med in this export)' from r
union all select 8, 'lng', lng::varchar, 'Original export', 'Plotted longitude (equals lng_med in this export)' from r
union all select 9, 'cluster', group_id::int::varchar, 'Original export', 'Group assignment; -1 = unclustered / noise' from r
union all select 10, 'address', coalesce(address, ''), 'Enrichment', 'Reverse-geocoded from lat/lng via OSM Nominatim' from r
union all select 11, 'group_label', group_label, 'Enrichment', 'Readable form of the cluster column' from r
union all select 12, 'active_days', (date_diff('day', first_seen::date, last_seen::date) + 1)::varchar, 'Derived', 'last_seen date − first_seen date + 1' from r
union all select 13, 'visits_per_week', round(visits / ((date_diff('day', first_seen::date, last_seen::date) + 1) / 7.0), 2)::varchar, 'Derived', 'points ÷ (active_days ÷ 7)' from r
union all select 14, 'visits_per_month', round(visits / ((date_diff('day', first_seen::date, last_seen::date) + 1) / 30.44), 1)::varchar, 'Derived', 'points ÷ (active_days ÷ 30.44)' from r
union all select 15, 'avg_days_between_visits', round((date_diff('day', first_seen::date, last_seen::date) + 1) / visits::float, 1)::varchar, 'Derived', 'active_days ÷ points' from r
order by ord
```

<DataTable data={full_record} rows=all>
    <Column id=field title="Field" />
    <Column id=value title="Value" wrap=true />
    <Column id=source title="Source" />
    <Column id=notes title="Meaning / formula" wrap=true />
</DataTable>

## How this location compares

```sql rank_context
with ranked as (
    select
        cluster_id::int as cluster_id, visits,
        row_number() over (order by visits desc) as visit_rank,
        count(*) over () as total_locations
    from visits.locations
)
select * from ranked
where cluster_id = try_cast('${params.cluster_id}' as int)
```

This location ranks **#{rank_context[0].visit_rank} of {rank_context[0].total_locations}** by visit count.

```sql same_group
select
    '/locations/' || cluster_id::int as location_link,
    cluster_id::int as cluster_id, address, visits,
    strftime(first_seen, '%Y-%m-%d') as first_date,
    strftime(last_seen, '%Y-%m-%d')  as last_date,
    case when cluster_id::int = try_cast('${params.cluster_id}' as int) then '→ this location' else '' end as marker
from visits.locations
where group_id = (select group_id from visits.locations where cluster_id::int = try_cast('${params.cluster_id}' as int))
order by visits desc
```

## Other locations in {location[0].group_label}

<DataTable data={same_group} link=location_link rows=15>
    <Column id=marker title="" />
    <Column id=cluster_id title="ID" />
    <Column id=address title="Address" wrap=true />
    <Column id=visits title="Visits" fmt=num0 contentType=colorscale />
    <Column id=first_date title="First visit" />
    <Column id=last_date title="Last visit" />
</DataTable>

> Per-visit timestamps are not present in the clustered export — first/last visit
> and rates above are exact; anything between them requires the raw visits file.
