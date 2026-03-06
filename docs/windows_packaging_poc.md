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

## Notes

- Runtime root is set via `LEX_MINT_RUNTIME_ROOT`.
- Packaged frontend hosting is enabled only when the packaging entrypoint sets `LEX_MINT_SERVE_FRONTEND=1`.
- This is a first packaging PoC, not an installer yet.
- Next step is to move writable runtime data to `%LOCALAPPDATA%\LexMint` for installer mode.
