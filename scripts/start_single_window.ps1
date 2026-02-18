$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $projectRoot
$projectName = Split-Path -Leaf $projectRoot

function Get-EnvValue {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Name
  )

  if (-not (Test-Path ".env")) {
    return $null
  }

  $line = Get-Content ".env" | Where-Object { $_ -match "^\s*${Name}\s*=" } | Select-Object -First 1
  if (-not $line) {
    return $null
  }

  return ($line -split "=", 2)[1].Trim()
}

Write-Host "========================================"
Write-Host "   LangGraph Agent - One Window Start"
Write-Host "========================================"
Write-Host ""

if (-not (Test-Path "venv\Scripts\python.exe")) {
  Write-Host "[ERROR] Virtual environment not found. Please run install.bat first"
  exit 1
}

if (-not (Test-Path "frontend\node_modules")) {
  Write-Host "[ERROR] Frontend dependencies not installed. Please run install.bat first"
  exit 1
}

if (-not (Test-Path ".env")) {
  Write-Host "[WARNING] .env file not found"
  Write-Host "[TIP] API keys are configured in $env:USERPROFILE\.lex_mint\keys_config.yaml"
  Write-Host ""
}

$apiPort = Get-EnvValue -Name "API_PORT"
if (-not $apiPort) {
  Write-Host "[ERROR] API_PORT not set in .env"
  exit 1
}

$frontendPort = Get-EnvValue -Name "FRONTEND_PORT"
if (-not $frontendPort) {
  Write-Host "[WARNING] FRONTEND_PORT not set in .env, fallback to 5173"
  $frontendPort = "5173"
}

$windowTitle = "$projectName FE:$frontendPort | BE:$apiPort"
$Host.UI.RawUI.WindowTitle = $windowTitle
[Console]::Title = $windowTitle

function Set-WindowTitle {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Title
  )

  try {
    $Host.UI.RawUI.WindowTitle = $Title
    [Console]::Title = $Title
  }
  catch {
    # Ignore non-console hosts.
  }
}

function Get-ProcessExitCodeOrNull {
  param(
    [Parameter(Mandatory = $true)]
    [System.Diagnostics.Process]$Process
  )

  try {
    return $Process.ExitCode
  }
  catch {
    return $null
  }
}

$srcDir = Join-Path $projectRoot "src"
$backendArgs = @(
  "-m",
  "uvicorn",
  "src.api.main:app",
  "--host",
  "0.0.0.0",
  "--port",
  $apiPort,
  "--reload",
  "--reload-dir",
  $srcDir
)

$viteScript = Join-Path $projectRoot "frontend\node_modules\vite\bin\vite.js"
if (-not (Test-Path $viteScript)) {
  Write-Host "[ERROR] Vite entry not found: $viteScript"
  Write-Host "[TIP] Run install.bat to install frontend dependencies"
  exit 1
}

$frontendArgs = @(
  $viteScript,
  "--host",
  "0.0.0.0",
  "--port",
  $frontendPort,
  "--strictPort"
)

$backendProcess = $null
$frontendProcess = $null
$exitCode = 0
$stopRequested = $false
$cancelHandler = $null

try {
  $cancelHandler = [ConsoleCancelEventHandler]{
    param($sender, $eventArgs)
    $eventArgs.Cancel = $true
    $script:stopRequested = $true
  }
  [Console]::add_CancelKeyPress($cancelHandler)

  Set-WindowTitle -Title $windowTitle

  Write-Host "[1/3] Starting backend service..."
  $backendProcess = Start-Process -FilePath ".\venv\Scripts\python.exe" -ArgumentList $backendArgs -NoNewWindow -PassThru
  Write-Host "      Backend:  http://localhost:$apiPort (PID $($backendProcess.Id))"
  Start-Sleep -Seconds 2

  Write-Host "[2/3] Starting frontend service..."
  $frontendProcess = Start-Process -FilePath "node.exe" -ArgumentList $frontendArgs -WorkingDirectory (Join-Path $projectRoot "frontend") -NoNewWindow -PassThru
  Write-Host "      Frontend: http://localhost:$frontendPort (PID $($frontendProcess.Id))"
  Start-Sleep -Seconds 2

  Write-Host "[3/3] Opening browser..."
  Start-Process "http://localhost:$frontendPort" | Out-Null

  Write-Host ""
  Write-Host "========================================"
  Write-Host "Services are running in this window."
  Write-Host "Press Ctrl+C to stop backend + frontend."
  Write-Host "========================================"
  Write-Host ""

  while ($true) {
    Start-Sleep -Seconds 1
    Set-WindowTitle -Title $windowTitle

    if ($stopRequested) {
      Write-Host ""
      Write-Host "[INFO] Ctrl+C detected, stopping services..."
      break
    }

    $backendProcess.Refresh()
    $frontendProcess.Refresh()

    if ($backendProcess.HasExited -or $frontendProcess.HasExited) {
      $backendExitCode = $null
      $frontendExitCode = $null
      if ($backendProcess.HasExited) {
        $backendExitCode = Get-ProcessExitCodeOrNull -Process $backendProcess
      }
      if ($frontendProcess.HasExited) {
        $frontendExitCode = Get-ProcessExitCodeOrNull -Process $frontendProcess
      }

      Write-Host ""
      if ($backendProcess.HasExited) {
        Write-Host "[WARN] Backend exited (PID $($backendProcess.Id), code $backendExitCode)"
      }
      if ($frontendProcess.HasExited) {
        Write-Host "[WARN] Frontend exited (PID $($frontendProcess.Id), code $frontendExitCode)"
      }

      if ($backendProcess.HasExited -and $frontendProcess.HasExited) {
        Write-Host "[INFO] Both services exited together. This usually means Ctrl+C was broadcast to both child processes."
      }
      else {
        Write-Host "[INFO] Service exit detected, stopping the other one..."
      }

      if ($backendProcess.HasExited -and $backendExitCode -ne $null -and $backendExitCode -ne 0) {
        $exitCode = $backendExitCode
      }
      if ($frontendProcess.HasExited -and $frontendExitCode -ne $null -and $frontendExitCode -ne 0) {
        $exitCode = $frontendExitCode
      }
      break
    }
  }
}
catch [System.Management.Automation.PipelineStoppedException] {
  Write-Host ""
  Write-Host "[INFO] Stop signal detected, stopping services..."
}
catch {
  $exitCode = 1
  Write-Host ""
  Write-Host "[ERROR] $($_.Exception.Message)"
}
finally {
  if ($cancelHandler) {
    [Console]::remove_CancelKeyPress($cancelHandler)
  }

  if ($backendProcess -and -not $backendProcess.HasExited) {
    Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    Wait-Process -Id $backendProcess.Id -ErrorAction SilentlyContinue
  }

  if ($frontendProcess -and -not $frontendProcess.HasExited) {
    Stop-Process -Id $frontendProcess.Id -Force -ErrorAction SilentlyContinue
    Wait-Process -Id $frontendProcess.Id -ErrorAction SilentlyContinue
  }
}

exit $exitCode
