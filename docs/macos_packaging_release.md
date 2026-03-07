# macOS Release Scaffold (.app + .dmg)

This flow builds a distributable `.app` bundle and `.dmg` from the macOS portable package.

## 1) Build .app and .dmg

Run from repo root:

```bash
./scripts/build_macos_release.sh --app-version 1.0.0
```

Default outputs:

- Portable runtime: `dist/macos_release/portable`
- App bundle: `dist/macos_release/Lex Mint.app`
- DMG: `dist/macos_release/Lex_Mint-1.0.0.dmg`

## 2) Common options

Reuse an existing portable package:

```bash
./scripts/build_macos_release.sh \
  --app-version 1.0.0 \
  --portable-dir dist/macos_poc \
  --skip-portable-build
```

Build app only (no dmg):

```bash
./scripts/build_macos_release.sh --app-version 1.0.0 --skip-dmg
```

Use custom metadata/icon:

```bash
./scripts/build_macos_release.sh \
  --app-name "Lex Mint" \
  --app-version 1.0.0 \
  --bundle-id com.lexmint.app \
  --icon /absolute/path/AppIcon.icns
```

## 3) Optional signing and notarization

Codesign app + notarize dmg (requires preconfigured keychain profile):

```bash
./scripts/build_macos_release.sh \
  --app-version 1.0.0 \
  --codesign-identity "Developer ID Application: Your Name (TEAMID)" \
  --notarize-profile "AC_NOTARY_PROFILE"
```

Notes:

- Without signing, app and dmg are still generated, but macOS may warn on first launch.
- `--notarize-profile` requires `--codesign-identity`.
- Notarization runs only when dmg output is enabled.

## 4) Result behavior

- Launching `Lex Mint.app` invokes the packaged runtime start script.
- Runtime data is still written to:
  - `~/Library/Application Support/LexMint`
