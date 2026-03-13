# Windows Packaging PoC (PyInstaller + Inno Setup)

> Updated: 2026-03-13
> Research Status: Historical reference (not source-of-truth for current implementation).
> Source-of-truth docs: `docs/backend_refactor_plan.md`, `docs/backend_module_responsibilities.md`, `docs/flow_event_protocol_v1.md`, `docs/api_endpoints.md`.

This Windows delivery flow now supports two outputs:

- Portable folder: `dist\windows_poc`
- Installer: `dist\installer\lex-mint-setup-<version>.exe`

The packaged app runs as a single backend process. `Vite` is only used to build the frontend bundle.

For macOS portable packaging, see `docs/research/packaging/macos_packaging_poc.md`.

## 1) Build Portable Package

Run from repo root:

```powershell
./scripts/build_windows.ps1
```

Optional custom API port and output path:

```powershell
./scripts/build_windows.ps1 -ApiPort 18080 -OutputDir "dist\windows_poc_custom"
```

## 2) Build Installer

Prerequisite: install Inno Setup 6 so `ISCC.exe` is available.

Then run:

```powershell
./scripts/build_windows_installer.ps1 -AppVersion 1.0.0
```

Optional flags:

```powershell
./scripts/build_windows_installer.ps1 -AppVersion 1.0.0 -SkipPyInstallerInstall
./scripts/build_windows_installer.ps1 -AppVersion 1.0.0 -SkipPortableBuild
./scripts/build_windows_installer.ps1 -IsccPath "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
```

## 3) Run Portable Package

```powershell
cd dist\windows_poc
.\start_lex_mint.bat
```

Then open:

- App: `http://127.0.0.1:<API_PORT>`
- Backend health: `http://127.0.0.1:<API_PORT>/api/health`

Stop the service:

```powershell
.\stop_lex_mint.bat
```

## Runtime Layout

Immutable packaged files stay under the install/output directory:

- `backend\`
- `frontend\dist`
- `config\defaults`
- `shared\schemas`
- `.env`

Writable runtime data is stored under `%LOCALAPPDATA%\LexMint` in packaged mode:

- `config\local`
- `data\state`
- `data\knowledge_bases`
- `conversations`
- `attachments`
- `logs`

Local GGUF models are resolved in this order:

- Absolute path from config
- `LEX_MINT_MODELS_ROOT`
- `%LOCALAPPDATA%\LexMint\models`
- `<install root>\models`

## Installer Behavior

The Inno Setup installer:

- installs files to `Program Files\Lex Mint`
- adds Start Menu shortcuts for start/stop/uninstall
- optionally adds a desktop shortcut
- can launch Lex Mint immediately after install
- keeps `%LOCALAPPDATA%\LexMint` user data outside the install directory

## Notes

- Runtime install root is set via `LEX_MINT_RUNTIME_ROOT`.
- Packaged frontend hosting is enabled only when the packaging entrypoint sets `LEX_MINT_SERVE_FRONTEND=1`.
- Packaged writable data defaults to `%LOCALAPPDATA%\LexMint` via `LEX_MINT_USER_DATA_ROOT`.
- This is now installer-ready packaging, but updater logic is still a separate next step.
