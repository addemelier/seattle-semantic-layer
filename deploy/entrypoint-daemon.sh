#!/bin/sh
# Dagster daemon: install the instance config, run the first pull if the lake has
# never had an accepted run (design D5, never fails: A9), then start the schedule.
set -eu
cp /app/deploy/dagster.yaml "$DAGSTER_HOME/dagster.yaml"
python -m permitmap.deploy.bootstrap
exec dagster-daemon run -w /app/deploy/workspace.yaml
