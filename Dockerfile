FROM node:22-bookworm-slim@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392 AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
WORKDIR /app
RUN python -m pip install --no-cache-dir uv==0.12.23
COPY pyproject.toml uv.lock ./
COPY src/ src/
RUN uv sync --frozen --no-dev
COPY migrations/ migrations/
COPY alembic.ini ./
COPY --from=web /web/dist/ web/dist/
RUN mkdir -p /data/blobs && chown -R 10001:10001 /data
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 RF_BLOB_ROOT=/data/blobs RF_WEB_DIST=/app/web/dist
USER 10001:10001
EXPOSE 8000
CMD ["researchflow","serve","--host","0.0.0.0"]
