Param(
    [string]$AppVersion = "1.0.0",
    [int]$ApiPort = 18000,
    [string]$PortableOutputDir = "dist\windows_poc",
    [string]$InstallerOutputDir = "dist\installer",
    [string]$IsccPath = "",
    [switch]$SkipFrontendBuild,
    [switch]$SkipPyInstallerInstall,
    [switch]$SkipPortableBuild
)

$ErrorActionPreference = "Stop"

function Resolve-IsccPath {
    Param(
        [string]$ExplicitPath
    )

    if ($ExplicitPath) {
        if (Test-Path $ExplicitPath) {
            return (Resolve-Path $ExplicitPath).Path
        }
        throw "ISCC.exe not found at explicit path: $ExplicitPath"
    }

    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidates = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    throw "ISCC.exe not found. Install Inno Setup 6 or pass -IsccPath."
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$portableOutput = Join-Path $repoRoot $PortableOutputDir
$installerOutput = Join-Path $repoRoot $InstallerOutputDir
$issPath = Join-Path $repoRoot "scripts\packaging\windows\inno\lex_mint.iss"

if (-not $SkipPortableBuild) {
    $buildArgs = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", (Join-Path $repoRoot "scripts\build_windows.ps1"),
        "-ApiPort", $ApiPort,
        "-OutputDir", $PortableOutputDir
    )
    if ($SkipFrontendBuild) {
        $buildArgs += "-SkipFrontendBuild"
    }
    if ($SkipPyInstallerInstall) {
        $buildArgs += "-SkipPyInstallerInstall"
    }

    Write-Host "[1/2] Building portable package..."
    & powershell.exe @buildArgs
}
else {
    Write-Host "[1/2] Skipped portable package build."
}

if (-not (Test-Path $portableOutput)) {
    throw "Portable package directory not found: $portableOutput"
}
if (-not (Test-Path $issPath)) {
    throw "Installer definition not found: $issPath"
}

$iscc = Resolve-IsccPath -ExplicitPath $IsccPath
New-Item -ItemType Directory -Force -Path $installerOutput | Out-Null

Write-Host "[2/2] Building installer with Inno Setup..."
& $iscc "/DAppVersion=$AppVersion" "/DSourceDir=$portableOutput" "/DInstallerOutputDir=$installerOutput" $issPath

Write-Host ""
Write-Host "Windows installer is ready."
Write-Host "- Installer: $installerOutput\lex-mint-setup-$AppVersion.exe"
Write-Host "- Portable package: $portableOutput"
