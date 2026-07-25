# AutoEq — fully autonomous Docker build
#
# Clones the repo from git, installs all dependencies, generates measurement
# data, builds the React frontend, and runs the whole thing behind uvicorn.
#
# Build:
#   docker build -t autoeq .
#
# Or with compose:
#   docker compose up --build

FROM python:3.11-slim-bookworm

# ---- system dependencies ----
# git      — clone the repo
# curl     — fetch NodeSource setup script
# libsndfile1 — required by soundfile (WAV/FLAC I/O)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git libsndfile1 ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# ---- Node.js 18.x (matches .nvmrc) ----
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# ---- clone repo ----
# Override REPO_URL / BRANCH at build time to point at a fork or pinned tag.
ARG REPO_URL=https://github.com/jaakkopasanen/AutoEq.git
ARG BRANCH=master
WORKDIR /app
RUN git clone --depth 1 --branch "${BRANCH}" "${REPO_URL}" .

# ---- setup (Python venv, pip deps, data generation, frontend build) ----
# This runs the --setup-only path of start.sh plus the production frontend build.
# It produces ~250 MB of measurement data, so it benefits from layer caching if
# you rebuild only the application layer.
RUN chmod +x start.sh && ./start.sh --setup-only --prod

# ---- runtime ----
# The container serves the API and built frontend on a single port.
EXPOSE 8000
CMD ["./start.sh", "--run-only", "--prod"]
