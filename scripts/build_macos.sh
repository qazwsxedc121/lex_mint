#!/usr/bin/env bash
set -euo pipefail

API_PORT=18000
OUTPUT_DIR="dist/macos_poc"
SKIP_FRONTEND_BUILD=0
SKIP_PYINSTALLER_INSTALL=0

usage() {
  cat <<'EOF'
Usage: scripts/build_macos.sh [options]

Options:
  --api-port PORT             API port written to packaged .env (default: 18000)
  --output-dir PATH           Output directory (default: dist/macos_poc)
  --skip-frontend-build       Skip frontend build step
  --skip-pyinstaller-install  Skip installing PyInstaller
  -h, --help                  Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-port)
      API_PORT="${2:-}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    --skip-frontend-build)
      SKIP_FRONTEND_BUILD=1
      shift
      ;;
    --skip-pyinstaller-install)
      SKIP_PYINSTALLER_INSTALL=1
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

if [[ ! "${API_PORT}" =~ ^[0-9]+$ ]]; then
  echo "Invalid --api-port value: ${API_PORT}" >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="${REPO_ROOT}/venv/bin/python"
FRONTEND_DIR="${REPO_ROOT}/frontend"
BACKEND_ENTRY="${REPO_ROOT}/scripts/packaging/macos/backend_entry.py"

if [[ ! -x "${VENV_PYTHON}" ]]; then
  echo "venv python not found at ${VENV_PYTHON}" >&2
  exit 1
fi
if [[ ! -d "${FRONTEND_DIR}" ]]; then
  echo "frontend directory not found: ${FRONTEND_DIR}" >&2
  exit 1
fi
if [[ ! -f "${BACKEND_ENTRY}" ]]; then
  echo "backend packaging entrypoint missing: ${BACKEND_ENTRY}" >&2
  exit 1
fi

echo "[1/5] Preparing dependencies..."
if [[ "${SKIP_PYINSTALLER_INSTALL}" == "0" ]]; then
  "${VENV_PYTHON}" -m pip install --disable-pip-version-check pyinstaller
fi

if [[ "${SKIP_FRONTEND_BUILD}" == "0" ]]; then
  echo "[2/5] Building frontend dist..."
  (
    cd "${FRONTEND_DIR}"
    VITE_USE_RELATIVE_API=1 npm run build
  )
else
  echo "[2/5] Skipped frontend build."
fi

FRONTEND_DIST="${FRONTEND_DIR}/dist"
if [[ ! -d "${FRONTEND_DIST}" ]]; then
  echo "frontend dist not found: ${FRONTEND_DIST}" >&2
  exit 1
fi

BUILD_ROOT="${REPO_ROOT}/build/macos_poc"
PYI_DIST="${BUILD_ROOT}/pyinstaller/dist"
PYI_WORK="${BUILD_ROOT}/pyinstaller/work"
PYI_SPEC="${BUILD_ROOT}/pyinstaller/spec"

echo "[3/5] Cleaning previous build artifacts..."
rm -rf "${BUILD_ROOT}"
mkdir -p "${PYI_DIST}" "${PYI_WORK}" "${PYI_SPEC}"

echo "[4/5] Building backend executable (PyInstaller)..."
"${VENV_PYTHON}" -m PyInstaller \
  --noconfirm \
  --clean \
  --onedir \
  --name "lex_mint_backend" \
  --paths "${REPO_ROOT}" \
  --collect-submodules src \
  "${BACKEND_ENTRY}" \
  --distpath "${PYI_DIST}" \
  --workpath "${PYI_WORK}/backend" \
  --specpath "${PYI_SPEC}"

OUTPUT_ROOT="${REPO_ROOT}/${OUTPUT_DIR}"
echo "[5/5] Assembling portable package at ${OUTPUT_ROOT}..."
rm -rf "${OUTPUT_ROOT}"
mkdir -p "${OUTPUT_ROOT}/backend" "${OUTPUT_ROOT}/frontend" "${OUTPUT_ROOT}/config" "${OUTPUT_ROOT}/shared"

cp -R "${PYI_DIST}/lex_mint_backend/." "${OUTPUT_ROOT}/backend/"
cp -R "${FRONTEND_DIST}" "${OUTPUT_ROOT}/frontend/dist"
cp -R "${REPO_ROOT}/config/defaults" "${OUTPUT_ROOT}/config/defaults"
cp -R "${REPO_ROOT}/shared/schemas" "${OUTPUT_ROOT}/shared/schemas"
cp "${REPO_ROOT}/scripts/packaging/macos/start_lex_mint.command" "${OUTPUT_ROOT}/start_lex_mint.command"
cp "${REPO_ROOT}/scripts/packaging/macos/stop_lex_mint.command" "${OUTPUT_ROOT}/stop_lex_mint.command"

chmod +x "${OUTPUT_ROOT}/start_lex_mint.command" "${OUTPUT_ROOT}/stop_lex_mint.command"

cat > "${OUTPUT_ROOT}/.env" <<EOF
API_HOST=127.0.0.1
API_PORT=${API_PORT}
UVICORN_LOG_LEVEL=info
EOF
cp "${OUTPUT_ROOT}/.env" "${OUTPUT_ROOT}/.env.example"

echo
echo "macOS packaging PoC is ready."
echo "- Start: ${OUTPUT_ROOT}/start_lex_mint.command"
echo "- Stop:  ${OUTPUT_ROOT}/stop_lex_mint.command"
echo "- App:   http://127.0.0.1:${API_PORT}"
echo "- User data: ~/Library/Application Support/LexMint"
