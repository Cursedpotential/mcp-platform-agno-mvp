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
