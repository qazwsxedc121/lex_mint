# macOS Packaging PoC (PyInstaller)

This macOS delivery flow produces a portable folder:

- Portable folder: `dist/macos_poc`

The packaged app runs as a single backend process and serves the built frontend from `frontend/dist`.

## 1) Build Portable Package

Run from repo root:

```bash
./scripts/build_macos.sh
```

Optional custom API port and output path:

```bash
./scripts/build_macos.sh --api-port 18080 --output-dir dist/macos_poc_custom
```

Optional skip flags:

```bash
./scripts/build_macos.sh --skip-frontend-build
./scripts/build_macos.sh --skip-pyinstaller-install
```

## 2) Run Portable Package

```bash
cd dist/macos_poc
./start_lex_mint.command
```

Then open:

- App: `http://127.0.0.1:<API_PORT>`
- Backend health: `http://127.0.0.1:<API_PORT>/api/health`

Stop the service:

```bash
./stop_lex_mint.command
```

## Runtime Layout

Immutable packaged files stay under the output directory:

- `backend/`
- `frontend/dist`
- `config/defaults`
- `shared/schemas`
- `.env`

Writable runtime data is stored under `~/Library/Application Support/LexMint` in packaged mode:

- `config/local`
- `data/state`
- `data/knowledge_bases`
- `conversations`
- `attachments`
- `logs`

Runtime launcher state files are also stored in the user data root:

- `run/lex_mint.pid`
- `logs/launcher_runtime.log`

Local GGUF models are resolved in this order:

- Absolute path from config
- `LEX_MINT_MODELS_ROOT`
- `~/Library/Application Support/LexMint/models`
- `<install root>/models`

## Notes

- Runtime install root is set via `LEX_MINT_RUNTIME_ROOT`.
- Packaged frontend hosting is enabled by `LEX_MINT_SERVE_FRONTEND=1` in the packaging entrypoint.
- Packaged writable data root is set via `LEX_MINT_USER_DATA_ROOT`.
- For `.app` and `.dmg` outputs, see `docs/macos_packaging_release.md`.
