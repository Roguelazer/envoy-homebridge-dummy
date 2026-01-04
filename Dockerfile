# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim

RUN <<EOF
    mkdir -p /app
    mkdir -p /data
    useradd appuser
    mkdir -p /home/appuser
    chown -R appuser: /home/appuser
    chown -R appuser: /data
EOF

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked --mount=type=cache,target=/var/lib/apt,sharing=locked <<EOF
    apt-get update
    apt-get upgrade -y
    apt-get install -y \
        ca-certificates \
        dumb-init \
        --no-install-recommends
    update-ca-certificates
EOF

WORKDIR /app

ENV UV_LINK_MODE=copy
RUN uv venv
# Install dependencies
RUN --mount=type=cache,target=/home/appuser/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY . /app
# Sync the project
RUN --mount=type=cache,target=/home/appuser/.cache/uv \
    uv sync --locked --no-dev

USER appuser
ENTRYPOINT ["/usr/bin/dumb-init"]
CMD ["uv", "run", "--no-dev", "main.py"]
