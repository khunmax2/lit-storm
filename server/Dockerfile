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
# Third-party packages first, from the lock alone: editing knowledge_storm or
# the README no longer reinstalls them, Chromium and the embedding model
# (about ten minutes a build).
COPY server/pyproject.toml server/uv.lock ./server/
RUN cd server && uv sync --frozen --no-dev --extra pdf --no-install-project --no-install-package knowledge-storm
RUN playwright install --with-deps chromium

# STORM's built-in embedding model, in the image: otherwise every new
# container fetched it from Hugging Face on its first Run, and every Run
# asked the Hub about it again (30 requests, seconds each Run), failing the
# article stage whenever the Hub could not be reached.
ENV HF_HOME=/opt/hf
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-MiniLM-L6-v2')" \
    && chmod -R a+rX /opt/hf
ENV HF_HUB_OFFLINE=1

# knowledge_storm, installed editable from here by the sync below.
COPY setup.py requirements.txt README.md ./
COPY knowledge_storm ./knowledge_storm

COPY server ./server
RUN cd server && uv sync --frozen --no-dev --extra pdf

WORKDIR /app/server
RUN useradd --create-home --uid 10001 litstorm && mkdir -p /data && chown litstorm /data
USER litstorm
ENV LITSTORM_DATA_DIR=/data

EXPOSE 8000
# The api service migrates, then serves. The worker service overrides this.
CMD ["sh", "-c", "alembic upgrade head && uvicorn litstorm.api:app --host 0.0.0.0 --port 8000 --proxy-headers"]
