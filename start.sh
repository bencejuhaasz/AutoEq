#!/usr/bin/env bash
# AutoEq startup script — sets up the environment, generates data, and launches
# both the backend API and frontend dev server.
#
# Usage:
#   ./start.sh              # full setup + start both services
#   ./start.sh --setup-only # only install deps and generate data
#   ./start.sh --run-only   # only start services (skip setup)
#   ./start.sh --backend    # start only the FastAPI backend
#   ./start.sh --frontend   # start only the React frontend
#   ./start.sh --prod       # production mode: build frontend, serve via backend
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/venv"
PYTHON="$VENV/bin/python"
WEBAPP="$ROOT/webapp"

# --------------- helpers ---------------
setup_only=false
run_only=false
backend_only=false
frontend_only=false
prod=false

for arg in "$@"; do
  case "$arg" in
    --setup-only) setup_only=true ;;
    --run-only)   run_only=true ;;
    --backend)    backend_only=true ;;
    --frontend)   frontend_only=true ;;
    --prod)       prod=true ;;
    *) echo "Unknown flag: $arg"; exit 1 ;;
  esac
done

if $backend_only && $frontend_only; then
  echo "Can't use --backend and --frontend together; just omit both to run everything."
  exit 1
fi

do_setup=true
do_backend=true
do_frontend=true

if $setup_only; then
  do_backend=false; do_frontend=false
fi
if $run_only; then
  do_setup=false
fi
if $backend_only; then
  do_setup=false; do_frontend=false
fi
if $frontend_only; then
  do_setup=false; do_backend=false
fi

# --------------- setup ---------------
if $do_setup; then
  echo "==> Checking Python version"
  PY_VER=$("$VENV/bin/python" --version 2>/dev/null || true)
  if [[ "$PY_VER" != *"3.11"* ]]; then
    echo "    Recreating venv with Python 3.11 (pyproject.toml requires <3.12)"

    # Try pyenv first, fall back to system python3.11, then error
    PY311=""
    if command -v pyenv &>/dev/null && pyenv which python3.11 &>/dev/null; then
      PY311="$(pyenv which python3.11)"
    elif command -v python3.11 &>/dev/null; then
      PY311="$(command -v python3.11)"
    else
      echo "ERROR: Python 3.11 not found. Install it via pyenv or your package manager."
      exit 1
    fi

    rm -rf "$VENV"
    "$PY311" -m venv "$VENV"
  fi
  PY_VER=$("$VENV/bin/python" --version)
  echo "    $PY_VER"

  echo "==> Installing AutoEq CLI (editable)"
  "$PYTHON" -m pip install -q -e "$ROOT"

  echo "==> Installing webapp dependencies"
  "$PYTHON" -m pip install -q -r "$WEBAPP/requirements.txt"

  # --------------- data generation ---------------
  # The webapp needs three JSON files in webapp/data/.  targets.json already
  # ships pre-built.  entries.json and measurements.json are generated from the
  # result CSVs in results/.  The upstream dbtools script pulls in pandas and
  # rapidfuzz which aren't in the core dependency list, so we use a self-
  # contained generator that only needs the autoeq package itself.

  ENTRIES="$WEBAPP/data/entries.json"
  MEASUREMENTS="$WEBAPP/data/measurements.json"
  GENERATOR="$WEBAPP/generate_data.py"

  # Regenerate if either file is missing OR generator script is newer
  NEED_GEN=false
  if [[ ! -f "$ENTRIES" ]] || [[ ! -f "$MEASUREMENTS" ]]; then
    NEED_GEN=true
  elif [[ "$GENERATOR" -nt "$ENTRIES" ]] || [[ "$GENERATOR" -nt "$MEASUREMENTS" ]]; then
    NEED_GEN=true
  fi

  if $NEED_GEN; then
    echo "==> Generating webapp data files (this reads all result CSVs — may take ~1 min)"
    "$PYTHON" "$GENERATOR"
  else
    echo "==> Webapp data files already up to date, skipping generation"
  fi

  # --------------- node / frontend ---------------
  # node_modules is gitignored and won't survive a git reset / fresh clone.
  # npm ci restores the exact tree from package-lock.json.
  echo "==> Checking Node.js"
  if ! command -v node &>/dev/null; then
    echo "ERROR: Node.js not found. Install it via nvm or your package manager."
    exit 1
  fi
  echo "    Node $(node --version), npm $(npm --version)"

  echo "==> Installing frontend dependencies"
  if [ -d "$WEBAPP/ui/node_modules" ]; then
    echo "    node_modules already present, skipping"
  else
    npm ci --prefix "$WEBAPP/ui" 2>&1 | sed 's/^/    /' || {
      echo "    npm ci failed, falling back to npm install"
      npm install --prefix "$WEBAPP/ui" 2>&1 | sed 's/^/    /'
    }
    echo "    node_modules ready"
  fi

  if $prod; then
    echo "==> Building frontend (production)"
    (cd "$WEBAPP/ui" && npm run build 2>&1 | sed 's/^/    /')
    echo "    frontend build ready"
  fi

  # --------------- runtime dirs ---------------
  mkdir -p "$WEBAPP/data/audio"
  mkdir -p "$WEBAPP/data/legal"

  echo "==> Setup complete"
fi

# --------------- run ---------------
if $do_backend || $do_frontend; then
  echo "==> Starting services (Ctrl-C to stop both)"

  cleanup() {
    echo ""
    echo "==> Stopping services..."
    # Kill the background job group
    kill 0 2>/dev/null || true
    wait 2>/dev/null || true
  }
  trap cleanup EXIT INT TERM
fi

if $do_backend; then
  if $prod; then
    echo "    Backend  → http://0.0.0.0:8000  (production — serving built frontend)"
    export APP_ENV=production
    (
      cd "$WEBAPP"
      "$VENV/bin/uvicorn" main:app --host 0.0.0.0 --port 8000 2>&1 | sed 's/^/[backend] /'
    ) &
  else
    echo "    Backend  → http://0.0.0.0:8000"
    (
      cd "$WEBAPP"
      "$VENV/bin/uvicorn" main:app --host 0.0.0.0 --port 8000 --reload 2>&1 | sed 's/^/[backend] /'
    ) &
  fi
fi

if $do_frontend && ! $prod; then
  echo "    Frontend → http://localhost:3000"
  (
    cd "$WEBAPP/ui"
    # Unset HOST because the shell may export it as the machine hostname,
    # which the CRA webpack dev server would try to bind to and fail.
    unset HOST
    PORT=3000 npm start 2>&1 | sed 's/^/[frontend] /'
  ) &
fi

# Wait for any background job (or the trap)
if $do_backend || $do_frontend; then
  wait
fi
