#!/bin/sh
# Dagster webserver, published on the server's loopback only (design A4).
set -eu
cp /app/deploy/dagster.yaml "$DAGSTER_HOME/dagster.yaml"
exec dagster-webserver -h 0.0.0.0 -p 3000 -w /app/deploy/workspace.yaml
