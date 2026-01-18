FROM python:3.13-alpine AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first
COPY uv.lock pyproject.toml ./

# Install dependencies with cache
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --no-editable

# Copy the entire project
COPY . /app

# Sync the project with cache
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-editable --no-dev

FROM python:3.13-alpine

RUN addgroup -S -g 1000 app && adduser -S -u 1000 -G app app

COPY --from=builder --chown=app:app /app/.venv /app/.venv

USER app

EXPOSE 22112

CMD ["/app/.venv/bin/kubernetes-metrics"]
