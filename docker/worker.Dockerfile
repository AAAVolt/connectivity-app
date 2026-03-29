# Build context: repo root (.)
FROM python:3.11-slim AS base

RUN groupadd -r app && useradd -r -g app -d /app app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app

RUN pip install --no-cache-dir poetry==1.8.3 \
    && poetry config virtualenvs.create false

# Install dependencies (cached layer)
COPY worker/pyproject.toml worker/poetry.lock* ./
RUN poetry install --no-interaction --no-ansi --no-root --only main

# Copy source and install package
COPY worker/ .
RUN poetry install --no-interaction --no-ansi --only main

RUN chown -R app:app /app
USER app
CMD ["python", "-m", "worker.cli", "hello"]
