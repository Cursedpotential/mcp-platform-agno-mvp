---
title: Visit Locations 2023
---

Clustered visit locations for January – December 2023, Genesee County (Flint), Michigan.
Addresses were reverse-geocoded from cluster coordinates via OpenStreetMap Nominatim.
Click any row to drill into a location; click a group to see its members. For the
untouched source data, every raw column, and how each metric is computed, see
[Data & provenance](/data).

```sql summary
select
    count(*)                              as locations,
    sum(visits)                           as total_visits,
    strftime(min(first_seen), '%Y-%m-%d') as earliest,
    strftime(max(last_seen), '%Y-%m-%d')  as latest
from visits.locations
```

<BigValue data={summary} value=locations title="Locations" />
<BigValue data={summary} value=total_visits fmt=num0 title="Total visits" />
<BigValue data={summary} value=earliest title="Earliest first-seen" />
<BigValue data={summary} value=latest title="Latest last-seen" />

```sql locations_enriched
select
    cluster_id::int as cluster_id,
    '/locations/' || cluster_id::int as location_link,
    address,
    coalesce(nullif(trim(split_part(address, ',', 1) || ' ' || split_part(address, ',', 2)), ''), 'Unknown') as short_address,
    group_id::int as group_id,
    group_label,
    '/groups/' || group_id::int as group_link,
    lat, lng, visits,
    strftime(first_seen, '%Y-%m-%d') as first_date,
    strftime(first_seen, '%H:%M')    as first_time,
    strftime(last_seen, '%Y-%m-%d')  as last_date,
    strftime(last_seen, '%H:%M')     as last_time,
    date_diff('day', first_seen::date, last_seen::date) + 1 as active_days,
    round(visits / ((date_diff('day', first_seen::date, last_seen::date) + 1) / 7.0), 2) as visits_per_week,
    round((date_diff('day', first_seen::date, last_seen::date) + 1) / visits::float, 1)  as avg_days_between_visits
from visits.locations
order by visits desc
```

## Where the visits happened

Bubble size = number of visits. Click a bubble to open that location's detail page.

<BubbleMap
    data={locations_enriched}
    lat=lat
    long=lng
    size=visits
    value=visits
    pointName=short_address
    link=location_link
    tooltipType=hover
    tooltip={[
        {id: 'short_address', showColumnName: false, valueClass: 'font-semibold'},
        {id: 'group_label', title: 'Group'},
        {id: 'visits', title: 'Visits', fmt: 'num0'},
        {id: 'first_date', title: 'First seen'},
        {id: 'last_date', title: 'Last seen'}
    ]}
/>

## Verification table — all locations

Every clustered location, sortable and searchable. Use this to double-check the
data: address, grouping, visit counts, and first/last visit date and time.

<DataTable data={locations_enriched} search=true rows=20 link=location_link>
    <Column id=cluster_id title="ID" />
    <Column id=address title="Address (normalized)" wrap=true />
    <Column id=group_label title="Group" />
    <Column id=visits title="Visits" fmt=num0 contentType=colorscale />
    <Column id=first_date title="First visit" />
    <Column id=first_time title="Time" />
    <Column id=last_date title="Last visit" />
    <Column id=last_time title="Time" />
    <Column id=active_days title="Active days" fmt=num0 />
    <Column id=visits_per_week title="Visits / wk" fmt=num2 />
</DataTable>

## Groups

```sql group_rollup
select
    group_label,
    '/groups/' || group_id::int as group_link,
    count(*)                              as member_locations,
    sum(visits)                           as total_visits,
    strftime(min(first_seen), '%Y-%m-%d') as earliest_first_seen,
    strftime(max(last_seen), '%Y-%m-%d')  as latest_last_seen
from visits.locations
group by group_label, group_id
order by group_id
```

<BarChart
    data={group_rollup}
    x=group_label
    y=total_visits
    swapXY=true
    title="Total visits by group"
/>

<DataTable data={group_rollup} link=group_link>
    <Column id=group_label title="Group" />
    <Column id=member_locations title="Locations" fmt=num0 />
    <Column id=total_visits title="Total visits" fmt=num0 />
    <Column id=earliest_first_seen title="Earliest first-seen" />
    <Column id=latest_last_seen title="Latest last-seen" />
</DataTable>

## Distribution & data-quality checks

```sql visit_distribution
select
    case
        when visits >= 500 then 'e. 500+'
        when visits >= 100 then 'd. 100–499'
        when visits >= 25  then 'c. 25–99'
        when visits >= 10  then 'b. 10–24'
        else 'a. 6–9'
    end            as visit_band,
    count(*)       as locations,
    sum(visits)    as total_visits
from visits.locations
group by 1
order by 1
```

<BarChart
    data={visit_distribution}
    x=visit_band
    y=locations
    title="Locations by visit-count band"
    subtitle="Most locations have few visits; a handful dominate the total"
/>

```sql quality_checks
select 'Locations with a missing address' as check, count(*) filter (where address is null or address = '') as flagged from visits.locations
union all
select 'Single-day locations (first = last visit date)', count(*) filter (where first_seen::date = last_seen::date) from visits.locations
union all
select 'Locations with first_seen after last_seen (impossible)', count(*) filter (where first_seen > last_seen) from visits.locations
union all
select 'Duplicate coordinates (same lat/lng twice)', count(*) - count(distinct lat || ',' || lng) from visits.locations
```

<DataTable data={quality_checks}>
    <Column id=check title="Check" wrap=true />
    <Column id=flagged title="Flagged rows" fmt=num0 contentType=colorscale colorScale=negative />
</DataTable>

```sql single_day
select
    '/locations/' || cluster_id::int as location_link,
    address, visits,
    strftime(first_seen, '%Y-%m-%d') as date,
    strftime(first_seen, '%H:%M')    as first_time,
    strftime(last_seen, '%H:%M')     as last_time
from visits.locations
where first_seen::date = last_seen::date
order by visits desc
```

{#if single_day.length > 0}

### Single-day locations

These clusters were only ever seen on one calendar day — worth eyeballing to
confirm they are real one-off stops rather than clustering artifacts.

<DataTable data={single_day} link=location_link>
    <Column id=address title="Address" wrap=true />
    <Column id=visits title="Visits" fmt=num0 />
    <Column id=date title="Date" />
    <Column id=first_time title="First time" />
    <Column id=last_time title="Last time" />
</DataTable>

{/if}

> **Note on drill-down depth:** this dataset is the *clustered* export — each row
> carries first-seen, last-seen, and a visit count, but not the individual visit
> timestamps. To drill down to actual per-visit dates, add the raw
> (pre-clustering) visits file as a second source in `sources/visits/`.
