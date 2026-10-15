# syntax=docker/dockerfile:1
FROM python:3.14-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=0 \
    UV_NO_CACHE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Copy dependency files first (layer cache optimisation)
COPY pyproject.toml uv.lock* ./

# Install production dependencies (no dev group)
RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev

# Copy the rest of the project
COPY . .
