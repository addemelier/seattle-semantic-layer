# One image for the app, the Dagster daemon and the Dagster webserver (design A1).
# Multi-arch: every dependency installs from arm64 and amd64 wheels
# (checked by `python -m permitmap.deploy.check_wheels`).
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml ./
COPY permitmap/ permitmap/
COPY dbt/ dbt/
COPY deploy/ deploy/
RUN pip install .

# Install the DuckDB extensions from their wheels at build time, never from the network at runtime.
RUN python -c "from permitmap.lake import load_extensions; load_extensions()"

# Dagster reads dbt/target/manifest.json; dbt deps only when the project has packages.
RUN if [ -f dbt/packages.yml ]; then dbt deps --project-dir dbt --profiles-dir dbt || true; fi
RUN dbt parse --project-dir dbt --profiles-dir dbt

# Non-root user that owns /data; dbt writes target/ under /app/dbt at runtime (design A10).
RUN useradd --uid 10001 --create-home app \
    && mkdir -p /data/lake /data/dagster \
    && chown -R app /data /app/dbt
USER app

ENV PERMITMAP_HOST=0.0.0.0 \
    PERMITMAP_PORT=8000 \
    PERMITMAP_LAKE_CATALOG=/data/lake/catalog.sqlite \
    PERMITMAP_LAKE_DATA=/data/lake/files \
    DAGSTER_HOME=/data/dagster
EXPOSE 8000
CMD ["python", "-m", "permitmap.app"]
