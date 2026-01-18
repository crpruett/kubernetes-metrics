FROM python:3.13-alpine AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY uv.lock pyproject.toml ./

RUN uv sync --locked --no-install-project --no-editable

COPY . /app

RUN uv sync --no-editable --no-dev

FROM python:3.13-alpine

RUN addgroup -S -g 1000 app && adduser -S -u 1000 -G app app

COPY --from=builder --chown=app:app /app/.venv /app/.venv

USER app

EXPOSE 22112

CMD ["/app/.venv/bin/kubernetes-metrics"]
#boop
