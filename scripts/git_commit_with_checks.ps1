param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$Message,
  [switch]$NoCommit
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$preCommitHome = Join-Path $repoRoot ".tmp\\precommit-cache"
$pythonExe = Join-Path $repoRoot "venv\\Scripts\\python.exe"

if (!(Test-Path $pythonExe)) {
  Write-Error "Python not found at $pythonExe"
}

if (!(Test-Path $preCommitHome)) {
  New-Item -ItemType Directory -Path $preCommitHome -Force | Out-Null
}

$env:PRE_COMMIT_HOME = $preCommitHome

Write-Host "[commit-check] PRE_COMMIT_HOME=$preCommitHome"
Write-Host "[commit-check] Running pre-commit..."
& $pythonExe -m pre_commit run
if ($LASTEXITCODE -ne 0) {
  Write-Error "pre-commit failed. Fix issues and retry."
}

if ($NoCommit) {
  Write-Host "[commit-check] NoCommit mode enabled, skipping git commit."
  exit 0
}

Write-Host "[commit-check] Running git commit..."
& git commit --no-verify -m $Message
if ($LASTEXITCODE -ne 0) {
  Write-Error "git commit failed."
}
