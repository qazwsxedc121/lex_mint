param(
    [int]$ApiPort = 8901,
    [int]$FrontendPort = 5181,
    [string]$SharedKeysPath = "$HOME\.lex_mint\keys_config.yaml",
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

function Set-OrAddEnvVar {
    param(
        [Parameter(Mandatory = $true)][string]$Content,
        [Parameter(Mandatory = $true)][string]$Key,
        [Parameter(Mandatory = $true)][string]$Value
    )

    $lines = @()
    if ($Content.Length -gt 0) {
        $lines = $Content -split "`r?`n"
    }

    $found = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^\s*$Key=") {
            $lines[$i] = "$Key=$Value"
            $found = $true
        }
    }

    if (-not $found) {
        $lines += "$Key=$Value"
    }

    return (($lines -join "`r`n").TrimEnd("`r", "`n") + "`r`n")
}

function Remove-ApiKeyEnvVars {
    param([Parameter(Mandatory = $true)][string]$Content)

    $lines = @()
    if ($Content.Length -gt 0) {
        $lines = $Content -split "`r?`n"
    }

    $kept = @()
    foreach ($line in $lines) {
        if ($line -match "^\s*[A-Za-z0-9_]*API_KEY=") {
            continue
        }
        $kept += $line
    }

    return (($kept -join "`r`n").TrimEnd("`r", "`n") + "`r`n")
}

function Has-SharedDeepSeekKey {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -Path $Path)) {
        return $false
    }

    $lines = Get-Content -Path $Path
    $inProviders = $false
    $inDeepSeek = $false

    foreach ($line in $lines) {
        if ($line -match "^\s*providers:\s*$") {
            $inProviders = $true
            $inDeepSeek = $false
            continue
        }
        if (-not $inProviders) {
            continue
        }
        if ($line -match "^\s{2}deepseek:\s*$") {
            $inDeepSeek = $true
            continue
        }
        if ($line -match "^\s{2}[A-Za-z0-9_-]+:\s*$" -and $line -notmatch "^\s{2}deepseek:\s*$") {
            $inDeepSeek = $false
            continue
        }
        if ($inDeepSeek -and $line -match "^\s{4}api_key:\s*(.+?)\s*$") {
            $value = $Matches[1].Trim().Trim('"').Trim("'")
            return $value -ne ""
        }
    }

    return $false
}

function Get-DeepSeekKeyFromKeysFile {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -Path $Path)) {
        return $null
    }

    $lines = Get-Content -Path $Path
    $inProviders = $false
    $inDeepSeek = $false

    foreach ($line in $lines) {
        if ($line -match "^\s*providers:\s*$") {
            $inProviders = $true
            $inDeepSeek = $false
            continue
        }
        if (-not $inProviders) {
            continue
        }
        if ($line -match "^\s{2}deepseek:\s*$") {
            $inDeepSeek = $true
            continue
        }
        if ($line -match "^\s{2}[A-Za-z0-9_-]+:\s*$" -and $line -notmatch "^\s{2}deepseek:\s*$") {
            $inDeepSeek = $false
            continue
        }
        if ($inDeepSeek -and $line -match "^\s{4}api_key:\s*(.+?)\s*$") {
            $value = $Matches[1].Trim().Trim('"').Trim("'")
            if ($value -ne "") {
                return $value
            }
        }
    }

    return $null
}

function Write-SharedKeysFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$DeepSeekKey
    )

    $safeKey = $DeepSeekKey.Replace('"', '\"')
    $content = @(
        "providers:",
        "  deepseek:",
        "    api_key: ""$safeKey"""
    ) -join "`r`n"

    $dir = Split-Path -Path $Path -Parent
    if (-not (Test-Path -Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    Set-Content -Path $Path -Value ($content + "`r`n")
}

function Get-WorktreePaths {
    $worktreeLines = git worktree list --porcelain 2>$null
    if ($LASTEXITCODE -ne 0) {
        return @()
    }
    $paths = @()
    foreach ($line in $worktreeLines) {
        if ($line -like "worktree *") {
            $paths += $line.Substring(9).Trim()
        }
    }
    return $paths
}

if (-not (Test-Path -Path ".\.env.example")) {
    throw "Run this script in repository root (missing .env.example)."
}

if (-not (Test-Path -Path ".\frontend\package.json")) {
    throw "Run this script in repository root (missing frontend/package.json)."
}

if (-not (Test-Path -Path ".\venv\Scripts\python.exe")) {
    Write-Host "[1/5] Creating virtual environment..."
    python -m venv .\venv --upgrade-deps
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create virtual environment."
    }
} else {
    Write-Host "[1/5] Virtual environment already exists, skip."
}

if (-not (Test-Path -Path ".\.env")) {
    Write-Host "[2/5] Creating .env from .env.example..."
    Copy-Item -Path ".\.env.example" -Destination ".\.env" -Force
} else {
    Write-Host "[2/5] .env already exists, updating required keys."
}

$envContent = Get-Content -Path ".\.env" -Raw
$envContent = Set-OrAddEnvVar -Content $envContent -Key "API_PORT" -Value "$ApiPort"

$origins = @(
    "http://localhost:$FrontendPort",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:$FrontendPort"
) | Select-Object -Unique
$corsOriginsJson = "[" + (($origins | ForEach-Object { '"' + $_ + '"' }) -join ",") + "]"
$envContent = Set-OrAddEnvVar -Content $envContent -Key "CORS_ORIGINS" -Value $corsOriginsJson
$envContent = Remove-ApiKeyEnvVars -Content $envContent
Set-Content -Path ".\.env" -Value $envContent

if (Has-SharedDeepSeekKey -Path $SharedKeysPath) {
    Write-Host "[3/5] Shared key file exists: $SharedKeysPath"
} else {
    $candidateKey = Get-DeepSeekKeyFromKeysFile -Path ".\config\local\keys_config.yaml"

    if (-not $candidateKey) {
        $currentPath = [System.IO.Path]::GetFullPath((Get-Location).Path)
        foreach ($worktreePath in Get-WorktreePaths) {
            $full = [System.IO.Path]::GetFullPath($worktreePath)
            if ($full -eq $currentPath) {
                continue
            }
            $candidatePath = Join-Path $full "config\local\keys_config.yaml"
            $candidateKey = Get-DeepSeekKeyFromKeysFile -Path $candidatePath
            if ($candidateKey) {
                break
            }
        }
    }

    if ($candidateKey) {
        Write-SharedKeysFile -Path $SharedKeysPath -DeepSeekKey $candidateKey
        Write-Host "[3/5] Shared key created from existing local keys config."
        Write-Host "      Path: $SharedKeysPath"
    } else {
        Write-Host "[3/5] Shared key missing."
        Write-Host "      Please create: $SharedKeysPath"
        Write-Host "      Example content:"
        Write-Host "      providers:"
        Write-Host "        deepseek:"
        Write-Host "          api_key: ""<your-key>"""
    }
}

if (-not $SkipInstall) {
    Write-Host "[4/5] Installing backend dependencies..."
    & .\venv\Scripts\pip.exe install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install backend dependencies."
    }

    Write-Host "[5/5] Installing frontend dependencies..."
    Push-Location .\frontend
    npm install
    $npmExitCode = $LASTEXITCODE
    Pop-Location
    if ($npmExitCode -ne 0) {
        throw "Failed to install frontend dependencies."
    }
} else {
    Write-Host "[4/5] Skip backend install (-SkipInstall)."
    Write-Host "[5/5] Skip frontend install (-SkipInstall)."
}

Write-Host ""
Write-Host "Done."
Write-Host "Backend start:  .\venv\Scripts\uvicorn src.api.main:app --host 0.0.0.0 --port $ApiPort"
Write-Host "Frontend start: cd frontend; npm run dev -- --host 0.0.0.0 --port $FrontendPort --strictPort"
