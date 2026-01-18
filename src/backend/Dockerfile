FROM python:3.13-alpine AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies in a cache layer with bind mounts
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --no-install-project --no-editable

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
