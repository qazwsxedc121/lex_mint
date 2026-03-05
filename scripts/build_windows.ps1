Param(
    [int]$ApiPort = 18000,
    [int]$FrontendPort = 18001,
    [string]$OutputDir = "dist\windows_poc",
    [switch]$SkipFrontendBuild,
    [switch]$SkipPyInstallerInstall
)

$ErrorActionPreference = "Stop"

function Assert-Exists {
    Param(
        [string]$PathValue,
        [string]$Message
    )
    if (-not (Test-Path $PathValue)) {
        throw $Message
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPython = Join-Path $repoRoot "venv\Scripts\python.exe"
$frontendDir = Join-Path $repoRoot "frontend"
$backendEntry = Join-Path $repoRoot "scripts\packaging\windows\backend_entry.py"
$frontendEntry = Join-Path $repoRoot "scripts\packaging\windows\frontend_server.py"

Assert-Exists $venvPython "venv python not found at $venvPython"
Assert-Exists $frontendDir "frontend directory not found: $frontendDir"
Assert-Exists $backendEntry "backend packaging entrypoint missing: $backendEntry"
Assert-Exists $frontendEntry "frontend packaging entrypoint missing: $frontendEntry"

Write-Host "[1/6] Preparing dependencies..."
if (-not $SkipPyInstallerInstall) {
    & $venvPython -m pip install --disable-pip-version-check pyinstaller
}

if (-not $SkipFrontendBuild) {
    Write-Host "[2/6] Building frontend dist..."
    Push-Location $frontendDir
    try {
        $env:VITE_API_URL = "http://127.0.0.1:$ApiPort"
        & npm run build
    }
    finally {
        Remove-Item Env:\VITE_API_URL -ErrorAction SilentlyContinue
        Pop-Location
    }
}
else {
    Write-Host "[2/6] Skipped frontend build."
}

$frontendDist = Join-Path $frontendDir "dist"
Assert-Exists $frontendDist "frontend dist not found: $frontendDist"

$buildRoot = Join-Path $repoRoot "build\windows_poc"
$pyiDist = Join-Path $buildRoot "pyinstaller\dist"
$pyiWork = Join-Path $buildRoot "pyinstaller\work"
$pyiSpec = Join-Path $buildRoot "pyinstaller\spec"

Write-Host "[3/6] Cleaning previous build artifacts..."
Remove-Item -Recurse -Force $buildRoot -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $pyiDist | Out-Null
New-Item -ItemType Directory -Path $pyiWork | Out-Null
New-Item -ItemType Directory -Path $pyiSpec | Out-Null

Write-Host "[4/6] Building backend executable (PyInstaller)..."
& $venvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --name "lex_mint_backend" `
    --paths $repoRoot `
    --collect-submodules src `
    $backendEntry `
    --distpath $pyiDist `
    --workpath (Join-Path $pyiWork "backend") `
    --specpath $pyiSpec

Write-Host "[5/6] Building frontend static server executable (PyInstaller)..."
& $venvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --name "lex_mint_frontend" `
    --paths $repoRoot `
    $frontendEntry `
    --distpath $pyiDist `
    --workpath (Join-Path $pyiWork "frontend") `
    --specpath $pyiSpec

$outputRoot = Join-Path $repoRoot $OutputDir
Write-Host "[6/6] Assembling portable package at $outputRoot..."
Remove-Item -Recurse -Force $outputRoot -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $outputRoot | Out-Null

$backendOut = Join-Path $outputRoot "backend"
$frontendOut = Join-Path $outputRoot "frontend"
New-Item -ItemType Directory -Path $backendOut | Out-Null
New-Item -ItemType Directory -Path $frontendOut | Out-Null

Copy-Item -Recurse -Force (Join-Path $pyiDist "lex_mint_backend\*") $backendOut
Copy-Item -Recurse -Force (Join-Path $pyiDist "lex_mint_frontend\*") $frontendOut
Copy-Item -Recurse -Force $frontendDist (Join-Path $frontendOut "dist")

Copy-Item -Recurse -Force (Join-Path $repoRoot "config\defaults") (Join-Path $outputRoot "config\defaults")
Copy-Item -Recurse -Force (Join-Path $repoRoot "shared\schemas") (Join-Path $outputRoot "shared\schemas")
Copy-Item -Force (Join-Path $repoRoot "scripts\packaging\windows\start_lex_mint.bat") $outputRoot
Copy-Item -Force (Join-Path $repoRoot "scripts\packaging\windows\stop_lex_mint.bat") $outputRoot

New-Item -ItemType Directory -Force -Path (Join-Path $outputRoot "config\local") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $outputRoot "data\state") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $outputRoot "data\chromadb") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $outputRoot "conversations") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $outputRoot "attachments") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $outputRoot "logs") | Out-Null

$envContent = @"
API_HOST=127.0.0.1
API_PORT=$ApiPort
FRONTEND_PORT=$FrontendPort
UVICORN_LOG_LEVEL=info
"@
$envContent | Set-Content -Path (Join-Path $outputRoot ".env") -Encoding ascii
$envContent | Set-Content -Path (Join-Path $outputRoot ".env.example") -Encoding ascii

Write-Host ""
Write-Host "Windows packaging PoC is ready."
Write-Host "Output: $outputRoot"
Write-Host "Run:    $outputRoot\start_lex_mint.bat"
