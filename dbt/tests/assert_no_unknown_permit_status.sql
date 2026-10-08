-- Warn when an open permit has a status in neither the closed nor the known-open set.
-- Such permits stay in the gold table (treated as open); this surfaces the new value
-- so the status sets can be updated.
{{ config(severity='warn') }}

select
    lower(trim(status_raw)) as status_norm,
    count(*)                as permits
from {{ ref('fct_open_permits') }}
where lower(trim(status_raw)) not in {{ status_list('closed_statuses') }}
  and lower(trim(status_raw)) not in {{ status_list('known_open_statuses') }}
group by 1
