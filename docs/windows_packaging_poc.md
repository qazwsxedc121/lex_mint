# Windows Packaging PoC (PyInstaller)

This PoC builds a portable Windows folder with:

- `backend\lex_mint_backend.exe` (FastAPI backend)
- `frontend\dist` (built frontend assets served by the backend)
- `start_lex_mint.bat` / `stop_lex_mint.bat`

`Vite` is only used to build the frontend bundle. The packaged app does not run a Vite dev server or a second frontend process.

## 1) Build

Run from repo root:

```powershell
./scripts/build_windows.ps1
```

Optional custom API port and output path:

```powershell
./scripts/build_windows.ps1 -ApiPort 18080 -OutputDir "dist\windows_poc_custom"
```

## 2) Run packaged app

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

## Notes

- Runtime install root is set via `LEX_MINT_RUNTIME_ROOT`.
- Packaged frontend hosting is enabled only when the packaging entrypoint sets `LEX_MINT_SERVE_FRONTEND=1`.
- Packaged writable data defaults to `%LOCALAPPDATA%\LexMint` via `LEX_MINT_USER_DATA_ROOT`.
- This is still a packaging PoC, not a full installer yet.
