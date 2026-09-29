# The API and the Worker: one image, two commands (docs/adr/0001).
# Built from the repository root, because it installs knowledge_storm from there:
#   docker build -f server/Dockerfile .
FROM python:3.12-slim

# Noto Sans Thai for the PDF export: Chromium prints with the fonts the
# machine has, and without a Thai one a Thai report prints as boxes.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

WORKDIR /app
# knowledge_storm first: it changes less than the server does.
COPY setup.py requirements.txt README.md ./
COPY knowledge_storm ./knowledge_storm
COPY server/pyproject.toml server/uv.lock ./server/
RUN cd server && uv sync --frozen --no-dev --extra pdf --no-install-project
RUN playwright install --with-deps chromium

COPY server ./server
RUN cd server && uv sync --frozen --no-dev --extra pdf

WORKDIR /app/server
RUN useradd --create-home --uid 10001 litstorm && mkdir -p /data && chown litstorm /data
USER litstorm
ENV LITSTORM_DATA_DIR=/data

EXPOSE 8000
# The api service migrates, then serves. The worker service overrides this.
CMD ["sh", "-c", "alembic upgrade head && uvicorn litstorm.api:app --host 0.0.0.0 --port 8000 --proxy-headers"]
