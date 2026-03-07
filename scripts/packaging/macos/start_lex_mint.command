#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${ROOT_DIR}"

export LEX_MINT_RUNTIME_ROOT="${ROOT_DIR}"
STATUS_FILE=""
OPEN_BROWSER=1
WAIT_HEALTH=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --status-file)
      STATUS_FILE="${2:-}"
      shift 2
      ;;
    --no-open)
      OPEN_BROWSER=0
      shift
      ;;
    --no-wait)
      WAIT_HEALTH=0
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

default_user_data_root() {
  printf '%s' "${HOME}/Library/Application Support/LexMint"
}

if [[ -z "${LEX_MINT_USER_DATA_ROOT:-}" ]]; then
  export LEX_MINT_USER_DATA_ROOT="$(default_user_data_root)"
fi

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
RUN_DIR="${LEX_MINT_USER_DATA_ROOT}/run"
LOG_DIR="${LEX_MINT_USER_DATA_ROOT}/logs"
PID_FILE="${RUN_DIR}/lex_mint.pid"
LOG_FILE="${LOG_DIR}/launcher_runtime.log"

mkdir -p "${RUN_DIR}" "${LOG_DIR}"

if [[ ! -x "${BACKEND_BIN}" ]]; then
  echo "[ERROR] backend executable not found: ${BACKEND_BIN}"
  exit 1
fi

if [[ -f "${PID_FILE}" ]]; then
  EXISTING_PID="$(cat "${PID_FILE}" 2>/dev/null || true)"
  if [[ -n "${EXISTING_PID}" ]] && kill -0 "${EXISTING_PID}" >/dev/null 2>&1; then
    if [[ -n "${STATUS_FILE}" ]]; then
      printf 'already_running:%s\n' "${EXISTING_PID}" > "${STATUS_FILE}"
    fi
    echo "Lex Mint is already running (pid ${EXISTING_PID})."
    if [[ "${OPEN_BROWSER}" == "1" ]]; then
      open "http://${API_HOST}:${API_PORT}" >/dev/null 2>&1 || true
    fi
    exit 0
  fi
  rm -f "${PID_FILE}"
fi

echo "Starting Lex Mint on ${API_HOST}:${API_PORT} ..."
nohup "${BACKEND_BIN}" >"${LOG_FILE}" 2>&1 &
PID="$!"
echo "${PID}" > "${PID_FILE}"
if [[ -n "${STATUS_FILE}" ]]; then
  printf 'started:%s\n' "${PID}" > "${STATUS_FILE}"
fi

if [[ "${WAIT_HEALTH}" == "1" ]]; then
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
fi

if [[ "${OPEN_BROWSER}" == "1" ]]; then
  open "http://${API_HOST}:${API_PORT}" >/dev/null 2>&1 || true
fi

echo
echo "Lex Mint started."
echo "- App:    http://${API_HOST}:${API_PORT}"
echo "- Health: http://${API_HOST}:${API_PORT}/api/health"
echo "- PID:    ${PID}"
echo "- Log:    ${LOG_FILE}"
echo "- Data:   ${LEX_MINT_USER_DATA_ROOT}"
echo
echo "To stop, run stop_lex_mint.command"
