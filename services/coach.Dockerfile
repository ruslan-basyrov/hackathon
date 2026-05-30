# Coach service — the simulation engine (state machine, signals, detection, policy,
# realize, runner). CPU-only; it reaches the model over HTTP. Build from repo root:
#   docker build -f services/coach.Dockerfile -t coach .
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY . .
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# Phase 1: runs the no-coach baseline and prints conversion. Override as phases land.
CMD ["python", "runner.py", "--config", "config.yaml"]
