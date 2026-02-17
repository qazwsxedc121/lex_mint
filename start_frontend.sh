#!/usr/bin/env bash
set -euo pipefail

FRONTEND_PORT=""
if [[ -f ".env" ]]; then
  FRONTEND_PORT=$(grep -E "^FRONTEND_PORT=" .env | head -n1 | cut -d= -f2- | tr -d '\r' || true)
fi
if [[ -z "${FRONTEND_PORT}" ]]; then
  echo "[WARN] FRONTEND_PORT is not set in .env, fallback to 5173"
  FRONTEND_PORT="5173"
fi

echo
echo "==============================================================================="
echo "Start Frontend Dev Server"
echo "==============================================================================="
echo

if [[ ! -d "frontend" ]]; then
  echo "frontend directory not found."
  exit 1
fi

cd "frontend"
echo "Frontend URL: http://localhost:${FRONTEND_PORT}"
npm run dev -- --host 0.0.0.0 --port "${FRONTEND_PORT}" --strictPort
