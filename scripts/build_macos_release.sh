#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Lex Mint"
APP_VERSION="1.0.0"
BUNDLE_ID="com.lexmint.app"
API_PORT=18000
OUTPUT_DIR="dist/macos_release"
PORTABLE_DIR=""
ICON_PATH=""
SKIP_PORTABLE_BUILD=0
SKIP_DMG=0
SKIP_FRONTEND_BUILD=0
SKIP_PYINSTALLER_INSTALL=0
CODESIGN_IDENTITY=""
NOTARIZE_PROFILE=""

usage() {
  cat <<'EOF'
Usage: scripts/build_macos_release.sh [options]

Options:
  --app-name NAME               App bundle name (default: "Lex Mint")
  --app-version VERSION         App version in Info.plist (default: 1.0.0)
  --bundle-id ID                Bundle identifier (default: com.lexmint.app)
  --api-port PORT               API port in packaged .env (default: 18000)
  --output-dir PATH             Release output dir (default: dist/macos_release)
  --portable-dir PATH           Existing portable dir; auto-generated when omitted
  --icon PATH                   Optional .icns path for app icon
  --skip-portable-build         Reuse --portable-dir (or output portable) without rebuilding
  --skip-dmg                    Build .app only (skip dmg)
  --skip-frontend-build         Passed through to scripts/build_macos.sh
  --skip-pyinstaller-install    Passed through to scripts/build_macos.sh
  --codesign-identity NAME      Optional codesign identity (Developer ID Application ...)
  --notarize-profile PROFILE    Optional keychain profile for xcrun notarytool
  -h, --help                    Show this help
EOF
}

require_cmd() {
  local cmd="$1"
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "Required command not found: ${cmd}" >&2
    exit 1
  fi
}

slugify() {
  local text="$1"
  text="${text// /_}"
  text="${text//[^A-Za-z0-9._-]/_}"
  printf '%s' "${text}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --app-name)
      APP_NAME="${2:-}"
      shift 2
      ;;
    --app-version)
      APP_VERSION="${2:-}"
      shift 2
      ;;
    --bundle-id)
      BUNDLE_ID="${2:-}"
      shift 2
      ;;
    --api-port)
      API_PORT="${2:-}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    --portable-dir)
      PORTABLE_DIR="${2:-}"
      shift 2
      ;;
    --icon)
      ICON_PATH="${2:-}"
      shift 2
      ;;
    --skip-portable-build)
      SKIP_PORTABLE_BUILD=1
      shift
      ;;
    --skip-dmg)
      SKIP_DMG=1
      shift
      ;;
    --skip-frontend-build)
      SKIP_FRONTEND_BUILD=1
      shift
      ;;
    --skip-pyinstaller-install)
      SKIP_PYINSTALLER_INSTALL=1
      shift
      ;;
    --codesign-identity)
      CODESIGN_IDENTITY="${2:-}"
      shift 2
      ;;
    --notarize-profile)
      NOTARIZE_PROFILE="${2:-}"
      shift 2
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

if [[ -n "${NOTARIZE_PROFILE}" && -z "${CODESIGN_IDENTITY}" ]]; then
  echo "--notarize-profile requires --codesign-identity." >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -z "${PORTABLE_DIR}" ]]; then
  PORTABLE_DIR="${OUTPUT_DIR}/portable"
fi

OUTPUT_ROOT="${REPO_ROOT}/${OUTPUT_DIR}"
PORTABLE_ROOT="${REPO_ROOT}/${PORTABLE_DIR}"
APP_DIR="${OUTPUT_ROOT}/${APP_NAME}.app"
APP_EXECUTABLE="lex_mint_launcher"
DMG_NAME="$(slugify "${APP_NAME}")-${APP_VERSION}.dmg"
DMG_PATH="${OUTPUT_ROOT}/${DMG_NAME}"

mkdir -p "${OUTPUT_ROOT}"

echo "[1/5] Preparing portable package..."
if [[ "${SKIP_PORTABLE_BUILD}" == "0" ]]; then
  BUILD_ARGS=(--api-port "${API_PORT}" --output-dir "${PORTABLE_DIR}")
  if [[ "${SKIP_FRONTEND_BUILD}" == "1" ]]; then
    BUILD_ARGS+=(--skip-frontend-build)
  fi
  if [[ "${SKIP_PYINSTALLER_INSTALL}" == "1" ]]; then
    BUILD_ARGS+=(--skip-pyinstaller-install)
  fi
  "${REPO_ROOT}/scripts/build_macos.sh" "${BUILD_ARGS[@]}"
else
  echo "Skipped portable build."
fi

if [[ ! -d "${PORTABLE_ROOT}" ]]; then
  echo "Portable package directory not found: ${PORTABLE_ROOT}" >&2
  exit 1
fi

echo "[2/5] Assembling .app bundle..."
rm -rf "${APP_DIR}"
mkdir -p "${APP_DIR}/Contents/MacOS" "${APP_DIR}/Contents/Resources"
cp -R "${PORTABLE_ROOT}" "${APP_DIR}/Contents/Resources/runtime"

cat > "${APP_DIR}/Contents/MacOS/${APP_EXECUTABLE}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RUNTIME_DIR="${SCRIPT_DIR}/../Resources/runtime"
START_SCRIPT="${RUNTIME_DIR}/start_lex_mint.command"
STOP_SCRIPT="${RUNTIME_DIR}/stop_lex_mint.command"

default_user_data_root() {
  printf '%s' "${HOME}/Library/Application Support/LexMint"
}

if [[ -z "${LEX_MINT_USER_DATA_ROOT:-}" ]]; then
  export LEX_MINT_USER_DATA_ROOT="$(default_user_data_root)"
fi

RUN_DIR="${LEX_MINT_USER_DATA_ROOT}/run"
PID_FILE="${RUN_DIR}/lex_mint.pid"
LOCK_DIR="${RUN_DIR}/app_controller.lock"
STATUS_FILE="${RUN_DIR}/launcher_start.status"
ENV_FILE="${RUNTIME_DIR}/.env"
mkdir -p "${RUN_DIR}"

read_pid() {
  if [[ -f "${PID_FILE}" ]]; then
    cat "${PID_FILE}" 2>/dev/null || true
  fi
}

read_env_value() {
  local key="$1"
  if [[ -f "${ENV_FILE}" ]]; then
    grep -E "^${key}=" "${ENV_FILE}" | head -n1 | cut -d= -f2- | tr -d '\r' || true
  fi
}

pid_running() {
  local pid="$1"
  [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1
}

if [[ ! -x "${START_SCRIPT}" ]]; then
  echo "Runtime start script missing: ${START_SCRIPT}" >&2
  exit 1
fi
if [[ ! -x "${STOP_SCRIPT}" ]]; then
  echo "Runtime stop script missing: ${STOP_SCRIPT}" >&2
  exit 1
fi

"${START_SCRIPT}" --status-file "${STATUS_FILE}" --no-open --no-wait || exit $?

START_MODE=""
START_PID=""
if [[ -f "${STATUS_FILE}" ]]; then
  STATUS_LINE="$(cat "${STATUS_FILE}" 2>/dev/null || true)"
  rm -f "${STATUS_FILE}"
  START_MODE="${STATUS_LINE%%:*}"
  START_PID="${STATUS_LINE#*:}"
fi

# If backend already existed before launch, do not keep a controller process.
if [[ "${START_MODE}" == "already_running" ]]; then
  exit 0
fi

if [[ "${START_MODE}" != "started" ]]; then
  START_MODE="started"
  START_PID="$(read_pid)"
fi

API_HOST="$(read_env_value "API_HOST")"
API_PORT="$(read_env_value "API_PORT")"
if [[ -z "${API_HOST}" ]]; then
  API_HOST="127.0.0.1"
fi
if [[ -z "${API_PORT}" ]]; then
  API_PORT="18000"
fi
open "http://${API_HOST}:${API_PORT}" >/dev/null 2>&1 || true

# If another controller instance is already active, just launch and exit.
if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
  exit 0
fi

cleanup() {
  rm -rf "${LOCK_DIR}" >/dev/null 2>&1 || true
  rm -f "${STATUS_FILE}" >/dev/null 2>&1 || true
  # Stop backend only when this app instance started a new backend process.
  if [[ "${START_MODE}" == "started" ]]; then
    "${STOP_SCRIPT}" >/dev/null 2>&1 || true
  fi
}

trap cleanup INT TERM EXIT

# Keep the app process alive so Cmd+Q/closing the app can trigger cleanup.
while true; do
  PID_NOW="$(read_pid)"
  if ! pid_running "${PID_NOW}"; then
    break
  fi
  sleep 2
done
EOF
chmod +x "${APP_DIR}/Contents/MacOS/${APP_EXECUTABLE}"

ICON_PLIST_KEY=""
if [[ -n "${ICON_PATH}" ]]; then
  if [[ ! -f "${ICON_PATH}" ]]; then
    echo "Icon file not found: ${ICON_PATH}" >&2
    exit 1
  fi
  cp "${ICON_PATH}" "${APP_DIR}/Contents/Resources/AppIcon.icns"
  ICON_PLIST_KEY="  <key>CFBundleIconFile</key>
  <string>AppIcon</string>"
fi

cat > "${APP_DIR}/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleDisplayName</key>
  <string>${APP_NAME}</string>
  <key>CFBundleExecutable</key>
  <string>${APP_EXECUTABLE}</string>
  <key>CFBundleIdentifier</key>
  <string>${BUNDLE_ID}</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>${APP_NAME}</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>${APP_VERSION}</string>
  <key>CFBundleVersion</key>
  <string>${APP_VERSION}</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.0</string>
${ICON_PLIST_KEY}
</dict>
</plist>
EOF

echo "[3/5] Optional signing..."
if [[ -n "${CODESIGN_IDENTITY}" ]]; then
  require_cmd codesign
  codesign --force --deep --options runtime --timestamp --sign "${CODESIGN_IDENTITY}" "${APP_DIR}"
  codesign --verify --deep --strict --verbose=2 "${APP_DIR}"
  spctl --assess --type execute --verbose "${APP_DIR}" || true
else
  echo "No --codesign-identity provided; app remains unsigned."
fi

echo "[4/5] Building dmg..."
if [[ "${SKIP_DMG}" == "0" ]]; then
  require_cmd hdiutil
  STAGE_DIR="${OUTPUT_ROOT}/_dmg_stage"
  rm -rf "${STAGE_DIR}" "${DMG_PATH}"
  mkdir -p "${STAGE_DIR}"
  cp -R "${APP_DIR}" "${STAGE_DIR}/"
  ln -s /Applications "${STAGE_DIR}/Applications"

  cat > "${STAGE_DIR}/README.txt" <<'EOF'
Drag the app to Applications, then launch it from there.
If macOS warns about an unidentified developer, use right-click -> Open once.
EOF

  hdiutil create \
    -volname "${APP_NAME}" \
    -srcfolder "${STAGE_DIR}" \
    -ov \
    -format UDZO \
    "${DMG_PATH}"

  rm -rf "${STAGE_DIR}"
else
  echo "Skipped dmg build."
fi

echo "[5/5] Optional notarization..."
if [[ -n "${NOTARIZE_PROFILE}" ]]; then
  if [[ "${SKIP_DMG}" == "1" ]]; then
    echo "Notarization requires dmg output; remove --skip-dmg." >&2
    exit 1
  fi
  require_cmd xcrun
  xcrun notarytool submit "${DMG_PATH}" --keychain-profile "${NOTARIZE_PROFILE}" --wait
  xcrun stapler staple "${APP_DIR}"
  xcrun stapler staple "${DMG_PATH}"
else
  echo "No --notarize-profile provided; skipped notarization."
fi

echo
echo "macOS release scaffold is ready."
echo "- Portable: ${PORTABLE_ROOT}"
echo "- App:      ${APP_DIR}"
if [[ "${SKIP_DMG}" == "0" ]]; then
  echo "- DMG:      ${DMG_PATH}"
fi
