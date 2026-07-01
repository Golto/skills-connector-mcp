FROM python:3.13-slim

# NOTE: kept intentionally minimal per the spec (7.2 - single fixed image,
# never chosen by the agent). Covers the common cases a skill script would
# need: git operations, HTTP calls, JSON/YAML parsing, and text processing.

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    jq \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    requests \
    pyyaml

WORKDIR /workspace
