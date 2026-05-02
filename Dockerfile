FROM node:22-bookworm-slim AS frontend-build

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PUNKAGENT_API_HOST=0.0.0.0 \
    PUNKAGENT_API_PORT=8000 \
    PUNKAGENT_FRONTEND_DIST=/app/frontend/dist \
    PUNKAGENT_ENABLE_DOCS=false \
    PUNKAGENT_ALLOWED_EMAILS=operti.felipe@proton.me

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg unixodbc-dev \
    && curl -sSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64,arm64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
        > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
COPY backend/pyproject.toml ./backend/pyproject.toml
COPY backend/src ./backend/src
COPY backend/README.md ./backend/README.md

RUN uv sync --frozen --no-dev --package punkathon-agent

COPY --from=frontend-build /app/frontend/dist ./frontend/dist

EXPOSE 8000

CMD ["/app/.venv/bin/punkagent", "api"]
