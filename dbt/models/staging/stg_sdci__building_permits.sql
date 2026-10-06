-- Silver: SDCI building permits, renamed to snake_case and typed.
-- One row per source row (dedupe happens in gold).

with source as (
    select * from {{ source('bronze', 'sdci_building_permits') }}
)

select
    trim(permitnum)                                   as permit_num,
    permitclass                                       as permit_class,
    permitclassmapped                                 as permit_class_mapped,
    permittypemapped                                  as permit_type_mapped,
    permittypedesc                                    as permit_type_desc,
    description                                       as description,
    try_cast(housingunitsremoved as integer)          as housing_units_removed,
    try_cast(housingunitsadded as integer)            as housing_units_added,
    try_cast(estprojectcost as decimal(18, 2))        as est_project_cost,
    try_cast(applieddate as date)                     as applied_date,
    try_cast(issueddate as date)                      as issued_date,
    try_cast(expiresdate as date)                     as expires_date,
    try_cast(completeddate as date)                   as completed_date,
    statuscurrent                                     as status_current,
    lower(trim(statuscurrent))                        as status_norm,
    originaladdress1                                  as address_line1,
    originalcity                                      as city,
    originalstate                                     as state,
    originalzip                                       as zip,
    nullif(trim(contractorcompanyname), '')           as contractor_company_name,
    link                                              as permit_url,
    try_cast(latitude as double)                      as latitude,
    try_cast(longitude as double)                     as longitude
from source
