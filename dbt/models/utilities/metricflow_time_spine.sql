-- Daily date spine required by dbt's semantic layer (MetricFlow) for any metric.
select cast(range as date) as date_day
from range(date '2000-01-01', date '2036-01-01', interval 1 day)
