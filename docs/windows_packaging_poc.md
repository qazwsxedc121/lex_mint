# Windows Packaging PoC (PyInstaller)

This PoC builds a portable Windows folder with:

- `backend\lex_mint_backend.exe` (FastAPI backend)
- `frontend\lex_mint_frontend.exe` (static server for `frontend/dist`)
- `start_lex_mint.bat` / `stop_lex_mint.bat`

## 1) Build

Run from repo root:

```powershell
./scripts/build_windows.ps1
```

Optional custom ports and output path:

```powershell
./scripts/build_windows.ps1 -ApiPort 18080 -FrontendPort 18081 -OutputDir "dist\windows_poc_custom"
```

## 2) Run packaged app

```powershell
cd dist\windows_poc
.\start_lex_mint.bat
```

Then open:

- Frontend: `http://127.0.0.1:<FRONTEND_PORT>`
- Backend health: `http://127.0.0.1:<API_PORT>/api/health`

Stop services:

```powershell
.\stop_lex_mint.bat
```

## Notes

- Runtime root is set via `LEX_MINT_RUNTIME_ROOT` (repo path helpers now support this).
- This is a first packaging PoC, not an installer yet.
- Next step is to move writable runtime data to `%LOCALAPPDATA%\LexMint` for installer mode.
