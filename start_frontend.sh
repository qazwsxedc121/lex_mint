#!/usr/bin/env bash
set -euo pipefail

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
npm run dev
