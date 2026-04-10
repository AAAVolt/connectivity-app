# Local development backend image – DuckDB-based, no PostGIS.
# Build context: repo root (.)
FROM python:3.11-slim AS base

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
