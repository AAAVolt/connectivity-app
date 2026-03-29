# Build context: repo root (.)
FROM python:3.11-slim AS base

RUN groupadd -r app && useradd -r -g app -d /app app
WORKDIR /app

RUN pip install --no-cache-dir poetry==1.8.3 \
    && poetry config virtualenvs.create false

# Install dependencies (cached layer)
COPY backend/pyproject.toml backend/poetry.lock* ./
RUN poetry install --no-interaction --no-ansi --no-root --only main

# Copy source and install package
COPY backend/ .
RUN poetry install --no-interaction --no-ansi --only main

RUN chown -R app:app /app
USER app
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
