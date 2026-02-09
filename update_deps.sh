#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo
echo "==============================================================================="
echo "Update Python and Node Dependencies"
echo "==============================================================================="
echo

if [[ ! -d "${ROOT_DIR}/venv" ]]; then
  echo "venv not found at ${ROOT_DIR}/venv"
  echo "Create it first (example): /opt/homebrew/bin/python3 -m venv venv"
  exit 1
fi

echo "[1/3] Upgrading pip..."
${ROOT_DIR}/venv/bin/python -m pip install --upgrade pip
echo "      done"
echo

echo "[2/3] Updating Python dependencies..."
${ROOT_DIR}/venv/bin/pip install --upgrade -r "${ROOT_DIR}/requirements.txt"
echo "      done"
echo

if [[ ! -d "${ROOT_DIR}/frontend" ]]; then
  echo "frontend directory not found at ${ROOT_DIR}/frontend"
  exit 1
fi

echo "[3/3] Updating Node dependencies..."
cd "${ROOT_DIR}/frontend"
npm install
npm update
echo "      done"
