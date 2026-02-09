#!/usr/bin/env bash
set -euo pipefail

API_PORT=""

if [[ -f ".env" ]]; then
  API_PORT=$(grep -E "^API_PORT=" .env | head -n1 | cut -d= -f2- || true)
fi

if [[ -z "${API_PORT}" ]]; then
  echo "API_PORT is not set. Please configure it in the root .env file."
  exit 1
fi

echo
echo "==============================================================================="
echo "Start Backend API Server (debug mode)"
echo "==============================================================================="
echo

echo "[1/2] Freeing port ${API_PORT}..."
if command -v lsof >/dev/null 2>&1; then
  PIDS=$(lsof -ti tcp:"${API_PORT}" || true)
  if [[ -n "${PIDS}" ]]; then
    echo "${PIDS}" | xargs -n1 echo "       Killing PID"
    echo "${PIDS}" | xargs kill -9
  fi
else
  echo "       lsof not found; skipping port cleanup"
fi
echo "      done"
echo

echo "[2/2] Starting server..."
echo
echo "==============================================================================="
echo "Server URL: http://0.0.0.0:${API_PORT}"
echo "Frontend URL: http://localhost:${API_PORT}"
echo "API Docs: http://localhost:${API_PORT}/docs"
echo
echo "Tip: set API_PORT in .env to change the port"
echo "==============================================================================="
echo

if [[ ! -d "venv" ]]; then
  echo "venv not found. Create it first."
  exit 1
fi

source "venv/bin/activate"
python run_server_debug.py
