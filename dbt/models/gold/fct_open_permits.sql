-- Gold: one row per open SDCI building permit.
-- "Open" = latest record for the permit is not in the closed status set.

with permits as (
    select * from {{ ref('stg_sdci__building_permits') }}
),

latest as (
    -- Dedupe: keep the most recently applied record, ties broken by latest issued date.
    select *
    from permits
    qualify row_number() over (
        partition by permit_num
        order by applied_date desc nulls last, issued_date desc nulls last
    ) = 1
),

open_permits as (
    select *
    from latest
    where status_norm not in {{ status_list('closed_statuses') }}
)

select
    permit_num                                          as permit_id,
    address_line1                                       as address,
    description,
    case
        when regexp_matches(coalesce(description, ''), '(?i)\b(a?adu|dadu)\b')
          or lower(coalesce(description, '')) like '%accessory dwelling%'
            then 'adu'
        when lower(coalesce(permit_type_mapped, '')) like '%demolition%'
          or lower(coalesce(permit_type_desc, '')) like '%demolition%'
            then 'demolition'
        when permit_type_desc = 'New'
          or lower(coalesce(permit_type_mapped, '')) like '%new%'
            then 'new_building'
        else 'addition_alteration'
    end                                                 as work_type,
    case when issued_date is null then 'in_review' else 'issued' end as stage,
    status_current                                      as status_raw,
    applied_date,
    issued_date,
    expires_date,
    est_project_cost                                    as valuation_usd,
    housing_units_added,
    housing_units_removed,
    contractor_company_name                             as contractor,
    permit_url,
    latitude,
    longitude
from open_permits
