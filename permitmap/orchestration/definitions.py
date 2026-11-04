"""Daily permits refresh: run: dagster dev -m permitmap.orchestration.definitions

One asset pulls, checks and swaps bronze by calling the same `run_ingest` the CLI
uses; the dbt models are dagster-dbt assets downstream of it. A rejected pull fails
the bronze asset, so dbt does not run and yesterday's gold stays up.

The dbt manifest must exist first: `dbt parse --project-dir dbt --profiles-dir dbt`.
"""

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dagster import (AssetExecutionContext, AssetSelection, AssetKey, DefaultScheduleStatus, Definitions,
                     MaterializeResult, ScheduleDefinition, asset, define_asset_job)
from dagster_dbt import DagsterDbtTranslator, DbtCliResource, DbtProject, dbt_assets

from permitmap.app.config import Config
from permitmap.ingest.pipeline import run_ingest

REPO = Path(__file__).resolve().parents[2]
DBT_DIR = REPO / "dbt"
BRONZE_ASSET = "bronze_sdci_building_permits"

dbt_project = DbtProject(project_dir=DBT_DIR, profiles_dir=DBT_DIR)


@asset(name=BRONZE_ASSET, group_name="ingest",
       description="Full SDCI permits snapshot from Socrata, guarded swap into lake.bronze.")
def bronze_sdci_building_permits(context: AssetExecutionContext) -> MaterializeResult:
    result = run_ingest(Config.from_env())  # raises IngestRejected (logged) on a bad pull
    context.log.info(result.summary())
    return MaterializeResult(metadata={
        "run_id": result.run_id, "rows_fetched": result.rows_fetched,
        "rows_valid": result.rows_valid, "rows_quarantined": result.rows_quarantined})


class _Translator(DagsterDbtTranslator):
    def get_asset_key(self, dbt_resource_props: Mapping[str, Any]) -> AssetKey:
        if (dbt_resource_props.get("resource_type") == "source"
                and dbt_resource_props.get("source_name") == "bronze"
                and dbt_resource_props.get("name") == "sdci_building_permits"):
            return AssetKey(BRONZE_ASSET)
        return super().get_asset_key(dbt_resource_props)


@dbt_assets(manifest=dbt_project.manifest_path, select="+fct_open_permits",
            dagster_dbt_translator=_Translator())
def permitmap_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    # dbt runs as a subprocess in dbt/; give its profile the same lake as the ingest.
    os.environ["PERMITMAP_LAKE_CATALOG"] = Path(Config.from_env().lake_catalog).resolve().as_posix()
    yield from dbt.cli(["build"], context=context).stream()


daily_permits_refresh = define_asset_job(
    "daily_permits_refresh", selection=AssetSelection.assets(bronze_sdci_building_permits, permitmap_dbt_assets))

daily_permits_refresh_schedule = ScheduleDefinition(
    name="daily_permits_refresh_schedule",
    job=daily_permits_refresh,
    cron_schedule="0 5 * * *",
    execution_timezone="America/Los_Angeles",
    default_status=DefaultScheduleStatus.RUNNING,
)

defs = Definitions(
    assets=[bronze_sdci_building_permits, permitmap_dbt_assets],
    jobs=[daily_permits_refresh],
    schedules=[daily_permits_refresh_schedule],
    resources={"dbt": DbtCliResource(project_dir=dbt_project)},
)
