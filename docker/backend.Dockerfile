# Local development backend image – DuckDB-based, no PostGIS.
# Build context: repo root (.)
# Base image pinned by digest — keep in sync with docker/cloudrun.Dockerfile.
FROM python:3.11-slim@sha256:6d85378d88a19cd4d76079817532d62232be95757cb45945a99fec8e8084b9c2 AS base

RUN groupadd -r app && useradd -r -g app -d /app app
WORKDIR /app

RUN pip install --no-cache-dir poetry==1.8.3

# Install dependencies (cached layer)
COPY backend/pyproject.toml backend/poetry.lock* ./
RUN poetry export --only main --without-hashes -f requirements.txt -o requirements.txt \
    && pip install --no-cache-dir -r requirements.txt

# Copy source and install package
COPY backend/ .
RUN pip install --no-cache-dir --no-deps .

RUN chown -R app:app /app
USER app
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
