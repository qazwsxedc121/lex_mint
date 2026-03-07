#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${ROOT_DIR}"

PID_FILE="${ROOT_DIR}/lex_mint.pid"

read_env_value() {
  local key="$1"
  if [[ -f ".env" ]]; then
    grep -E "^${key}=" ".env" | head -n1 | cut -d= -f2- | tr -d '\r' || true
  fi
}

API_PORT="$(read_env_value "API_PORT")"
if [[ -z "${API_PORT}" ]]; then
  API_PORT="18000"
fi

stop_pid() {
  local pid="$1"
  if ! kill -0 "${pid}" >/dev/null 2>&1; then
    return
  fi
  kill "${pid}" >/dev/null 2>&1 || true
  for _ in $(seq 1 20); do
    if ! kill -0 "${pid}" >/dev/null 2>&1; then
      return
    fi
    sleep 0.15
  done
  kill -9 "${pid}" >/dev/null 2>&1 || true
}

if [[ -f "${PID_FILE}" ]]; then
  PID="$(cat "${PID_FILE}" 2>/dev/null || true)"
  if [[ -n "${PID}" ]]; then
    echo "Stopping Lex Mint pid ${PID} ..."
    stop_pid "${PID}"
  fi
  rm -f "${PID_FILE}"
fi

if command -v lsof >/dev/null 2>&1; then
  PORT_PIDS="$(lsof -ti tcp:${API_PORT} -sTCP:LISTEN || true)"
  if [[ -n "${PORT_PIDS}" ]]; then
    echo "${PORT_PIDS}" | while IFS= read -r pid; do
      [[ -z "${pid}" ]] && continue
      echo "Stopping process on port ${API_PORT}: pid ${pid}"
      stop_pid "${pid}"
    done
  fi
fi

echo "Done."
