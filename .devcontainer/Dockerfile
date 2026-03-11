FROM python:3.14-bookworm

# Minimal tooling for development workflows
RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Poetry is required for this project's workflow
RUN pip install --no-cache-dir --upgrade pip poetry

# Snyk CLI for security scanning
RUN npm install -g snyk

WORKDIR /workspaces/attest
