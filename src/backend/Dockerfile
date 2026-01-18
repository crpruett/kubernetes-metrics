FROM python:3.13-alpine AS builder

#Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

#Change the working directory to the 'app' directory
WORKDIR /app

#Install dependencies in a cache layer. This speeds up build time.
#RUN --mount=type=cache,target=/root/.cache/uv \
#--mount=type=bind,source=uv.lock,target=uv.lock \
#--mount=type=bind,source=pyproject.toml,target=pyproject.toml \
#uv sync --no-install-project # add --locked and --no-editable later

#Copy the project into the intermediate image
COPY . /app

#Sync the project and install it, now that we have access to the source code
RUN --mount=type=cache,target=root/.cache/uv \
uv sync --locked --no-editable --no-dev

FROM python:3.13-alpine

#Create a non-root user and group with specific IDs
RUN addgroup -S -g 1000 app && adduser -S -u 1000 -G app app

#Copy the env, but not the source code
COPY --from=builder --chown=app:app /app/.venv /app/.venv

#Switch  to non-root user
USER app

# Expose the correct port, though this is already done in our code
EXPOSE 22112 

#Run the application
CMD ["/app/.venv/bin/kubernetes-metrics"]

