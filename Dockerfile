# The app itself, as an image. Everything else this deployment runs —
# Supabase, SearXNG, the Deep Research UI — was already a container; the one
# piece that mattered most was a process on somebody's host, with no image to
# pin, no healthcheck, and a 1.3GB virtualenv to rebuild on a new machine.
#
# Build from the repository root:
#
#     docker build -t lit-storm/app:$(git rev-parse --short HEAD) .
#
# It does not carry secrets.toml and must not: `auth.setting` falls through to
# the environment for exactly this reason, so a deployment passes keys as
# environment variables and the image stays the same everywhere.

# ---------------------------------------------------------------- builder
FROM python:3.14-slim AS builder

# Wheels for 3.14 are new enough that a package without one has to be built
# here rather than fail the build. None of this reaches the final image.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Torch first, and from the CPU index. sentence-transformers pulls it in, and
# left to itself pip takes the CUDA build: about 2.5GB of nvidia libraries for
# a machine with no GPU. Asked for explicitly it is ~480MB, and the later
# install sees the requirement already satisfied.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch

# Dependencies before source, so editing a page does not reinstall torch.
COPY requirements.txt ./
COPY frontend/demo_light/requirements.txt ./frontend-requirements.txt
RUN pip install -r requirements.txt -r frontend-requirements.txt

# `knowledge_storm` has to be importable from inside frontend/demo_light,
# which is where the app runs from. --no-deps because requirements.txt is
# already installed above and setup.py would only resolve it again.
COPY setup.py README.md ./
COPY knowledge_storm ./knowledge_storm
RUN pip install --no-deps .

# STORM's article stage ranks snippets with a local sentence-transformer, and
# fetches it the first time it runs. Fetched here instead: otherwise the first
# research of every fresh container stalls on a download, and a deployment
# that cannot reach huggingface.co fails at the one point in a run where the
# work so far is already expensive.
ENV HF_HOME=/opt/hf
RUN python -c "from sentence_transformers import SentenceTransformer; \
SentenceTransformer('paraphrase-MiniLM-L6-v2')"

# ---------------------------------------------------------------- runtime
FROM python:3.14-slim AS runtime

LABEL org.opencontainers.image.title="lit-storm" \
      org.opencontainers.image.description="STORM and Co-STORM research app" \
      org.opencontainers.image.source="https://github.com/khunmax2/lit-storm"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    # The settings the admin pages write. Inside the source tree by default,
    # which a volume cannot mount over without taking config.toml — and the
    # app's theme — with it.
    STORM_STATE_DIR=/data/state \
    # Streamlit writes here and would otherwise try the home directory of a
    # user it does not have.
    HOME=/data \
    # Read-only, and outside /data on purpose: the model came with the image,
    # so a deployment that wipes its volume does not have to fetch it again.
    HF_HOME=/opt/hf \
    # Baking the model in is not enough on its own. Left to itself the hub
    # client still calls huggingface.co to check the cached copy — which
    # cost 11.5s with a network and hung indefinitely without one, and
    # logged a permission error trying to write a marker into a cache this
    # user cannot write to. Offline it reads the cache and nothing else:
    # 6.3s with no network at all. Nothing else here fetches from the hub.
    HF_HUB_OFFLINE=1

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/hf /opt/hf

# knowledge_storm is installed into the venv by the builder, so it is not
# copied here — two copies of it on one image invites edits to the one that
# is not imported.
WORKDIR /app
COPY frontend ./frontend

# Not root, and the two writable paths are the only two it owns. Reports live
# inside the source tree because `get_demo_dir()` puts them there; the
# directory is created now so a mount is not needed for the app to start.
RUN useradd --create-home --uid 10001 storm \
    && mkdir -p /data/state /app/frontend/demo_light/DEMO_WORKING_DIR \
    && chown -R storm:storm /data /app/frontend/demo_light/DEMO_WORKING_DIR
USER storm

VOLUME ["/data", "/app/frontend/demo_light/DEMO_WORKING_DIR"]

EXPOSE 8501

# Streamlit's own readiness endpoint. No curl in slim, and adding one to ask a
# question Python can ask is a package more than the image needs.
# Follows STREAMLIT_SERVER_BASE_URL_PATH: served under a base path, "/"
# is a 404 and the container would report unhealthy while serving every
# request put to it. 127.0.0.1 rather than localhost for the same reason
# the edge's check uses it — localhost can resolve to ::1 first.
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD ["python", "-c", "import os,sys,urllib.request; base=os.environ.get('STREAMLIT_SERVER_BASE_URL_PATH','').strip('/'); root='/'+base if base else ''; sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:8501{root}/_stcore/health', timeout=4).status == 200 else 1)"]

WORKDIR /app/frontend/demo_light

# No --server.runOnSave: there is no one here to save a file, and it would
# destroy a Co-STORM run in progress if there were. Headless stops Streamlit
# opening a browser and asking for an email on first run.
CMD ["streamlit", "run", "storm.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
