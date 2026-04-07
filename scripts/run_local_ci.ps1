param(
  [switch]$SkipInstall,
  [switch]$SkipBackend,
  [switch]$SkipFrontend,
  [switch]$IncludeSmoke
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$frontendRoot = Join-Path $repoRoot "frontend"
$pythonExe = Join-Path $repoRoot "venv/Scripts/python.exe"
$pipExe = Join-Path $repoRoot "venv/Scripts/pip.exe"
$pytestExe = Join-Path $repoRoot "venv/Scripts/pytest.exe"

function Invoke-CheckedCommand {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$Exe,
    [Parameter(Mandatory = $true)][string[]]$Args,
    [Parameter(Mandatory = $false)][string]$WorkingDirectory = $repoRoot
  )

  Push-Location $WorkingDirectory
  try {
    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Exe @Args
    if ($LASTEXITCODE -ne 0) {
      throw "$Name failed with exit code $LASTEXITCODE"
    }
  } finally {
    Pop-Location
  }
}

if (-not (Test-Path $pythonExe)) {
  throw "Missing venv Python: $pythonExe"
}
if (-not (Test-Path $pipExe)) {
  throw "Missing venv pip: $pipExe"
}
if (-not (Test-Path $pytestExe)) {
  throw "Missing venv pytest: $pytestExe"
}

$env:API_PORT = "18080"
$env:FRONTEND_PORT = "13000"
$env:PYTHONUTF8 = "1"

if (-not $SkipBackend) {
  if (-not $SkipInstall) {
    Invoke-CheckedCommand -Name "Upgrade pip" -Exe $pythonExe -Args @("-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel")
    Invoke-CheckedCommand -Name "Install backend dependencies" -Exe $pipExe -Args @("install", "-r", "requirements.txt")
    Invoke-CheckedCommand -Name "Install typecheck dependencies" -Exe "npm" -Args @("ci")
  }

  Invoke-CheckedCommand -Name "Check workflow schema" -Exe $pythonExe -Args @("scripts/generate_workflow_schema.py", "--check")
  Invoke-CheckedCommand -Name "Ruff check" -Exe $pythonExe -Args @("-m", "ruff", "check", ".")
  Invoke-CheckedCommand -Name "Ruff format check" -Exe $pythonExe -Args @("-m", "ruff", "format", "--check", ".")
  Invoke-CheckedCommand -Name "Mypy" -Exe $pythonExe -Args @("-m", "mypy", "src")
  Invoke-CheckedCommand -Name "BasedPyright" -Exe "npm" -Args @("run", "typecheck")
  Invoke-CheckedCommand -Name "Backend HTTP contract tests" -Exe $pytestExe -Args @("--no-cov", "tests/unit/api/routers/test_message_http_contract.py")
  Invoke-CheckedCommand -Name "Pytest" -Exe $pytestExe -Args @("tests", "--ignore=tests/e2e", "--ignore=tests/test_function_calling.py")
}

if (-not $SkipFrontend) {
  if (-not $SkipInstall) {
    Invoke-CheckedCommand -Name "Install frontend dependencies" -Exe "npm" -Args @("ci") -WorkingDirectory $frontendRoot
  }

  Invoke-CheckedCommand -Name "Frontend lint" -Exe "npm" -Args @("run", "lint") -WorkingDirectory $frontendRoot
  Invoke-CheckedCommand -Name "Frontend unit coverage" -Exe "npm" -Args @("run", "test:coverage") -WorkingDirectory $frontendRoot
  Invoke-CheckedCommand -Name "Frontend API contract tests" -Exe "npm" -Args @("run", "test", "--", "tests/unit/services") -WorkingDirectory $frontendRoot
  Invoke-CheckedCommand -Name "Frontend build" -Exe "npm" -Args @("run", "build") -WorkingDirectory $frontendRoot
}

if ($IncludeSmoke) {
  if (-not $SkipInstall) {
    Invoke-CheckedCommand -Name "Install Playwright chromium" -Exe "npx" -Args @("playwright", "install", "chromium") -WorkingDirectory $frontendRoot
  }
  Invoke-CheckedCommand -Name "Frontend smoke e2e" -Exe "npm" -Args @("run", "test:e2e:smoke") -WorkingDirectory $frontendRoot
}

Write-Host ""
Write-Host "Local CI checks completed successfully." -ForegroundColor Green
