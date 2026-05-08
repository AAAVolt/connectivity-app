# Worker image – DuckDB/GeoPandas-based, no PostGIS.
# Build context: repo root (.)
# Base image pinned by digest — keep in sync with the other Python images.
FROM python:3.11-slim@sha256:6d85378d88a19cd4d76079817532d62232be95757cb45945a99fec8e8084b9c2 AS base

RUN groupadd -r app && useradd -r -g app -d /app app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app

RUN pip install --no-cache-dir poetry==1.8.3

# Install dependencies (cached layer)
COPY worker/pyproject.toml worker/poetry.lock* ./
RUN poetry export --only main --without-hashes -f requirements.txt -o requirements.txt \
    && pip install --no-cache-dir -r requirements.txt

# Copy source and install package
COPY worker/ .
RUN pip install --no-cache-dir --no-deps .

RUN chown -R app:app /app
USER app
CMD ["python", "-m", "worker.cli", "hello"]
