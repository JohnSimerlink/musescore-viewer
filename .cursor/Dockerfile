# Cursor Cloud Agent base image (dev tooling only).
# Do not COPY the project — Cursor checks out the selected commit itself.
FROM node:22-bookworm-slim

RUN apt-get update \
  && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    python3 \
    python3-pip \
    python3-venv \
    sudo \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
