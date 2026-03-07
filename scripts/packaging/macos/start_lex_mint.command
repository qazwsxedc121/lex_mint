#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${ROOT_DIR}"

export LEX_MINT_RUNTIME_ROOT="${ROOT_DIR}"

if [[ ! -f ".env" && -f ".env.example" ]]; then
  cp ".env.example" ".env"
fi

read_env_value() {
  local key="$1"
  if [[ -f ".env" ]]; then
    grep -E "^${key}=" ".env" | head -n1 | cut -d= -f2- | tr -d '\r' || true
  fi
}

API_HOST="$(read_env_value "API_HOST")"
API_PORT="$(read_env_value "API_PORT")"
if [[ -z "${API_HOST}" ]]; then
  API_HOST="127.0.0.1"
fi
if [[ -z "${API_PORT}" ]]; then
  API_PORT="18000"
fi

BACKEND_BIN="${ROOT_DIR}/backend/lex_mint_backend"
PID_FILE="${ROOT_DIR}/lex_mint.pid"
LOG_FILE="${ROOT_DIR}/lex_mint_runtime.log"

if [[ ! -x "${BACKEND_BIN}" ]]; then
  echo "[ERROR] backend executable not found: ${BACKEND_BIN}"
  exit 1
fi

if [[ -f "${PID_FILE}" ]]; then
  EXISTING_PID="$(cat "${PID_FILE}" 2>/dev/null || true)"
  if [[ -n "${EXISTING_PID}" ]] && kill -0 "${EXISTING_PID}" >/dev/null 2>&1; then
    echo "Lex Mint is already running (pid ${EXISTING_PID})."
    open "http://${API_HOST}:${API_PORT}" >/dev/null 2>&1 || true
    exit 0
  fi
  rm -f "${PID_FILE}"
fi

echo "Starting Lex Mint on ${API_HOST}:${API_PORT} ..."
nohup "${BACKEND_BIN}" >"${LOG_FILE}" 2>&1 &
PID="$!"
echo "${PID}" > "${PID_FILE}"

READY=0
for _ in $(seq 1 40); do
  if curl -fsS "http://${API_HOST}:${API_PORT}/api/health" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 0.25
done

if [[ "${READY}" == "0" ]]; then
  echo "[WARN] Backend health check did not pass in time."
fi

open "http://${API_HOST}:${API_PORT}" >/dev/null 2>&1 || true

echo
echo "Lex Mint started."
echo "- App:    http://${API_HOST}:${API_PORT}"
echo "- Health: http://${API_HOST}:${API_PORT}/api/health"
echo "- PID:    ${PID}"
echo "- Log:    ${LOG_FILE}"
echo
echo "To stop, run stop_lex_mint.command"
