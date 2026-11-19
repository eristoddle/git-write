# GitWrite sync server: one image, no database, no sidecars.
# Runs plain HTTP inside the container — TLS, domain and port are the
# reverse proxy's job. Repos and tokens live on the /data volume.
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY gitwrite_cli ./gitwrite_cli
COPY gitwrite_core ./gitwrite_core
COPY gitwrite_server ./gitwrite_server

RUN pip install --no-cache-dir .

ENV GITWRITE_REPOS_ROOT=/data/repos \
    GITWRITE_TOKEN_FILE=/data/tokens

RUN mkdir -p /data/repos
VOLUME /data

EXPOSE 8080

CMD ["python", "-m", "gitwrite_server", "serve"]
