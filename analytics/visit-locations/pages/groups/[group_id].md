```sql group_info
select
    group_label,
    count(*)                              as member_locations,
    sum(visits)                           as total_visits,
    strftime(min(first_seen), '%Y-%m-%d') as earliest_first_seen,
    strftime(max(last_seen), '%Y-%m-%d')  as latest_last_seen
from visits.locations
where group_id::int = try_cast('${params.group_id}' as int)
group by group_label
```

# {group_info[0].group_label}

<BigValue data={group_info} value=member_locations fmt=num0 title="Locations" />
<BigValue data={group_info} value=total_visits fmt=num0 title="Total visits" />
<BigValue data={group_info} value=earliest_first_seen title="Earliest first-seen" />
<BigValue data={group_info} value=latest_last_seen title="Latest last-seen" />

```sql members
select
    '/locations/' || cluster_id::int as location_link,
    cluster_id::int as cluster_id, address,
    coalesce(nullif(trim(split_part(address, ',', 1) || ' ' || split_part(address, ',', 2)), ''), 'Unknown') as short_address,
    lat, lng, visits,
    strftime(first_seen, '%Y-%m-%d') as first_date,
    strftime(first_seen, '%H:%M')    as first_time,
    strftime(last_seen, '%Y-%m-%d')  as last_date,
    strftime(last_seen, '%H:%M')     as last_time,
    round(visits / ((date_diff('day', first_seen::date, last_seen::date) + 1) / 7.0), 2) as visits_per_week
from visits.locations
where group_id::int = try_cast('${params.group_id}' as int)
order by visits desc
```

<BubbleMap
    data={members}
    lat=lat
    long=lng
    size=visits
    value=visits
    pointName=short_address
    link=location_link
    tooltipType=hover
    tooltip={[
        {id: 'short_address', showColumnName: false, valueClass: 'font-semibold'},
        {id: 'visits', title: 'Visits', fmt: 'num0'}
    ]}
/>

## Member locations

<DataTable data={members} link=location_link search=true rows=20>
    <Column id=cluster_id title="ID" />
    <Column id=address title="Address" wrap=true />
    <Column id=visits title="Visits" fmt=num0 contentType=colorscale />
    <Column id=first_date title="First visit" />
    <Column id=first_time title="Time" />
    <Column id=last_date title="Last visit" />
    <Column id=last_time title="Time" />
    <Column id=visits_per_week title="Visits / wk" fmt=num2 />
</DataTable>
