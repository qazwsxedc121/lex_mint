#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

API_BASE=19000
FRONTEND_BASE=15100
SLOT_MIN=1
SLOT_MAX=999

API_PORT=""
FRONTEND_PORT=""
SLOT=""
PYTHON_BIN=""
SHARED_KEYS_PATH="${HOME}/.lex_mint/keys_config.yaml"
SKIP_INSTALL=0

usage() {
  cat <<'EOF'
Usage:
  scripts/init_worktree.sh [--slot N]
  scripts/init_worktree.sh --api-port PORT --frontend-port PORT

Options:
  --slot N                  Slot index (1-999). Maps to API=19000+N, FRONTEND=15100+N.
  --api-port PORT           API port (required with --frontend-port unless --slot is set).
  --frontend-port PORT      Frontend port (required with --api-port unless --slot is set).
  --shared-keys-path PATH   Shared bootstrap keys path (default: $HOME/.lex_mint/keys_config.yaml).
  --python-bin BIN          Python binary for creating venv when missing.
  --skip-install            Skip backend/frontend dependency installation.
  -h, --help                Show this help.

Notes:
  - If no slot/ports are provided, the script auto-selects the first free slot.
  - The script never writes to the shared keys file.
EOF
}

is_int() {
  [[ "${1:-}" =~ ^[0-9]+$ ]]
}

contains_value() {
  local needle="$1"
  shift || true
  local item
  for item in "$@"; do
    if [[ "${item}" == "${needle}" ]]; then
      return 0
    fi
  done
  return 1
}

port_is_in_use() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1
    return $?
  fi

  "${PYTHON_BIN:-python3}" - "$port" <<'PY' >/dev/null 2>&1
import socket
import sys

port = int(sys.argv[1])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(0.2)
try:
    in_use = s.connect_ex(("127.0.0.1", port)) == 0
finally:
    s.close()
raise SystemExit(0 if in_use else 1)
PY
}

read_env_key() {
  local file="$1"
  local key="$2"
  if [[ ! -f "${file}" ]]; then
    return 0
  fi
  grep -E "^${key}=" "${file}" | head -n1 | cut -d= -f2- | tr -d '\r' || true
}

get_worktree_paths() {
  git -C "${ROOT_DIR}" worktree list --porcelain 2>/dev/null | awk '/^worktree /{print substr($0,10)}'
}

ensure_repo_root() {
  if [[ ! -f "${ROOT_DIR}/.env.example" ]]; then
    echo "Run this script from repository context (missing .env.example)." >&2
    exit 1
  fi
  if [[ ! -f "${ROOT_DIR}/frontend/package.json" ]]; then
    echo "Run this script from repository context (missing frontend/package.json)." >&2
    exit 1
  fi
}

pick_python_bin() {
  if [[ -n "${PYTHON_BIN}" ]]; then
    if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
      echo "Python binary not found: ${PYTHON_BIN}" >&2
      exit 1
    fi
    return
  fi

  local candidate
  for candidate in python3.12 python3.11 python3.10 python3; do
    if command -v "${candidate}" >/dev/null 2>&1; then
      PYTHON_BIN="${candidate}"
      return
    fi
  done

  echo "No suitable python binary found (tried python3.12/python3.11/python3.10/python3)." >&2
  exit 1
}

resolve_ports_from_slot() {
  API_PORT="$((API_BASE + SLOT))"
  FRONTEND_PORT="$((FRONTEND_BASE + SLOT))"
}

resolve_slot_from_ports() {
  if [[ -z "${API_PORT}" || -z "${FRONTEND_PORT}" ]]; then
    return
  fi

  local api_slot="$((API_PORT - API_BASE))"
  local fe_slot="$((FRONTEND_PORT - FRONTEND_BASE))"
  if (( api_slot == fe_slot && api_slot >= SLOT_MIN && api_slot <= SLOT_MAX )); then
    SLOT="${api_slot}"
  fi
}

collect_used_data() {
  USED_SLOTS=()
  USED_API_PORTS=()
  USED_FRONTEND_PORTS=()

  local current_root
  current_root="$(cd "${ROOT_DIR}" && pwd)"
  local wt_path env_file wt_api wt_fe wt_slot_api wt_slot_fe

  while IFS= read -r wt_path; do
    [[ -z "${wt_path}" ]] && continue
    wt_path="$(cd "${wt_path}" && pwd)"
    if [[ "${wt_path}" == "${current_root}" ]]; then
      continue
    fi

    env_file="${wt_path}/.env"
    wt_api="$(read_env_key "${env_file}" "API_PORT")"
    wt_fe="$(read_env_key "${env_file}" "FRONTEND_PORT")"

    if is_int "${wt_api}"; then
      USED_API_PORTS+=("${wt_api}")
    fi
    if is_int "${wt_fe}"; then
      USED_FRONTEND_PORTS+=("${wt_fe}")
    fi

    if is_int "${wt_api}" && is_int "${wt_fe}"; then
      wt_slot_api="$((wt_api - API_BASE))"
      wt_slot_fe="$((wt_fe - FRONTEND_BASE))"
      if (( wt_slot_api == wt_slot_fe && wt_slot_api >= SLOT_MIN && wt_slot_api <= SLOT_MAX )); then
        USED_SLOTS+=("${wt_slot_api}")
      fi
    fi
  done < <(get_worktree_paths)
}

auto_pick_slot() {
  local s api fe
  for ((s = SLOT_MIN; s <= SLOT_MAX; s++)); do
    if [[ ${#USED_SLOTS[@]} -gt 0 ]] && contains_value "${s}" "${USED_SLOTS[@]}"; then
      continue
    fi

    api="$((API_BASE + s))"
    fe="$((FRONTEND_BASE + s))"

    if [[ ${#USED_API_PORTS[@]} -gt 0 ]] && contains_value "${api}" "${USED_API_PORTS[@]}"; then
      continue
    fi
    if [[ ${#USED_FRONTEND_PORTS[@]} -gt 0 ]] && contains_value "${fe}" "${USED_FRONTEND_PORTS[@]}"; then
      continue
    fi
    if port_is_in_use "${api}"; then
      continue
    fi
    if port_is_in_use "${fe}"; then
      continue
    fi

    SLOT="${s}"
    resolve_ports_from_slot
    return
  done

  echo "No free slot found in range ${SLOT_MIN}-${SLOT_MAX}." >&2
  exit 1
}

validate_inputs() {
  if [[ -n "${SLOT}" ]]; then
    if ! is_int "${SLOT}" || (( SLOT < SLOT_MIN || SLOT > SLOT_MAX )); then
      echo "Invalid slot '${SLOT}'. Expected ${SLOT_MIN}-${SLOT_MAX}." >&2
      exit 1
    fi
    resolve_ports_from_slot
  elif [[ -n "${API_PORT}" || -n "${FRONTEND_PORT}" ]]; then
    if [[ -z "${API_PORT}" || -z "${FRONTEND_PORT}" ]]; then
      echo "Both --api-port and --frontend-port are required." >&2
      exit 1
    fi
    if ! is_int "${API_PORT}" || ! is_int "${FRONTEND_PORT}"; then
      echo "Ports must be numeric." >&2
      exit 1
    fi
    resolve_slot_from_ports
  else
    auto_pick_slot
  fi

  if [[ ${#USED_API_PORTS[@]} -gt 0 ]] && contains_value "${API_PORT}" "${USED_API_PORTS[@]}"; then
    echo "API port ${API_PORT} is already used by another worktree." >&2
    exit 1
  fi
  if [[ ${#USED_FRONTEND_PORTS[@]} -gt 0 ]] && contains_value "${FRONTEND_PORT}" "${USED_FRONTEND_PORTS[@]}"; then
    echo "Frontend port ${FRONTEND_PORT} is already used by another worktree." >&2
    exit 1
  fi
  if port_is_in_use "${API_PORT}"; then
    echo "API port ${API_PORT} is already in use by another process." >&2
    exit 1
  fi
  if port_is_in_use "${FRONTEND_PORT}"; then
    echo "Frontend port ${FRONTEND_PORT} is already in use by another process." >&2
    exit 1
  fi
}

upsert_env() {
  local env_path="$1"
  ENV_PATH="${env_path}" \
  API_PORT_VALUE="${API_PORT}" \
  FRONTEND_PORT_VALUE="${FRONTEND_PORT}" \
  CORS_ORIGINS_VALUE="[\"http://localhost:${FRONTEND_PORT}\",\"http://localhost:3000\",\"http://127.0.0.1:${FRONTEND_PORT}\"]" \
  "${PYTHON_BIN}" <<'PY'
import os
from pathlib import Path

path = Path(os.environ["ENV_PATH"])
updates = {
    "API_PORT": os.environ["API_PORT_VALUE"],
    "FRONTEND_PORT": os.environ["FRONTEND_PORT_VALUE"],
    "CORS_ORIGINS": os.environ["CORS_ORIGINS_VALUE"],
}

lines = path.read_text(encoding="utf-8").splitlines()
out = []
seen = set()

for line in lines:
    stripped = line.lstrip()
    if "=" in line and not stripped.startswith("#"):
        key = line.split("=", 1)[0].strip()
        if key.endswith("API_KEY"):
            continue
        if key in updates:
            out.append(f"{key}={updates[key]}")
            seen.add(key)
            continue
    out.append(line)

for key, value in updates.items():
    if key not in seen:
        out.append(f"{key}={value}")

path.write_text("\n".join(out).rstrip("\n") + "\n", encoding="utf-8")
PY
}

ensure_local_keys() {
  local local_keys_path="${ROOT_DIR}/config/local/keys_config.yaml"
  local bootstrap_source=""
  local current_root wt_path candidate

  if [[ -f "${local_keys_path}" ]]; then
    echo "[3/5] Local key file exists: ${local_keys_path}"
    echo "      Shared key file is bootstrap-only: ${SHARED_KEYS_PATH}"
    return
  fi

  if [[ -f "${SHARED_KEYS_PATH}" ]]; then
    bootstrap_source="${SHARED_KEYS_PATH}"
  else
    current_root="$(cd "${ROOT_DIR}" && pwd)"
    while IFS= read -r wt_path; do
      [[ -z "${wt_path}" ]] && continue
      wt_path="$(cd "${wt_path}" && pwd)"
      if [[ "${wt_path}" == "${current_root}" ]]; then
        continue
      fi
      candidate="${wt_path}/config/local/keys_config.yaml"
      if [[ -f "${candidate}" ]]; then
        bootstrap_source="${candidate}"
        break
      fi
    done < <(get_worktree_paths)
  fi

  mkdir -p "${ROOT_DIR}/config/local"
  if [[ -n "${bootstrap_source}" ]]; then
    cp "${bootstrap_source}" "${local_keys_path}"
    echo "[3/5] Local key file initialized."
    echo "      Source: ${bootstrap_source}"
    echo "      Target: ${local_keys_path}"
    echo "      Shared key file is never modified by this script."
  else
    printf 'providers: {}\n' > "${local_keys_path}"
    echo "[3/5] No bootstrap key file found."
    echo "      Created empty local key file: ${local_keys_path}"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --slot)
      SLOT="${2:-}"
      shift 2
      ;;
    --api-port)
      API_PORT="${2:-}"
      shift 2
      ;;
    --frontend-port)
      FRONTEND_PORT="${2:-}"
      shift 2
      ;;
    --shared-keys-path)
      SHARED_KEYS_PATH="${2:-}"
      shift 2
      ;;
    --python-bin)
      PYTHON_BIN="${2:-}"
      shift 2
      ;;
    --skip-install)
      SKIP_INSTALL=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

ensure_repo_root
collect_used_data
pick_python_bin
validate_inputs

if [[ -n "${SLOT}" ]]; then
  echo "Using slot ${SLOT} -> API_PORT=${API_PORT}, FRONTEND_PORT=${FRONTEND_PORT}"
else
  echo "Using custom ports API_PORT=${API_PORT}, FRONTEND_PORT=${FRONTEND_PORT}"
fi

if [[ ! -x "${ROOT_DIR}/venv/bin/python" ]]; then
  echo "[1/5] Creating virtual environment (${PYTHON_BIN})..."
  "${PYTHON_BIN}" -m venv "${ROOT_DIR}/venv" --upgrade-deps
else
  echo "[1/5] Virtual environment already exists, skip."
fi

if [[ ! -f "${ROOT_DIR}/.env" ]]; then
  echo "[2/5] Creating .env from .env.example..."
  cp "${ROOT_DIR}/.env.example" "${ROOT_DIR}/.env"
else
  echo "[2/5] .env already exists, updating required keys."
fi
upsert_env "${ROOT_DIR}/.env"

ensure_local_keys

if [[ "${SKIP_INSTALL}" == "0" ]]; then
  echo "[4/5] Installing backend dependencies..."
  "${ROOT_DIR}/venv/bin/pip" install -r "${ROOT_DIR}/requirements.txt"

  echo "[5/5] Installing frontend dependencies..."
  (
    cd "${ROOT_DIR}/frontend"
    npm install
  )
else
  echo "[4/5] Skip backend install (--skip-install)."
  echo "[5/5] Skip frontend install (--skip-install)."
fi

echo
echo "Done."
echo "Backend start:  ${ROOT_DIR}/venv/bin/uvicorn src.api.main:app --host 0.0.0.0 --port ${API_PORT}"
echo "Frontend start: cd ${ROOT_DIR}/frontend && npm run dev -- --host 0.0.0.0 --port ${FRONTEND_PORT} --strictPort"
