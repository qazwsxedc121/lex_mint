param(
    [string]$EnvFile = ".env",
    [switch]$DryRun,
    [int]$MaxPasses = 5,
    [int]$RetryDelayMs = 400
)

$ErrorActionPreference = "Stop"

function Resolve-EnvFilePath {
    param([string]$Path)

    if ([System.IO.Path]::IsPathRooted($Path)) {
        if (Test-Path -Path $Path) {
            return (Resolve-Path -Path $Path).Path
        }
        return $null
    }

    $candidates = @((Join-Path -Path (Get-Location) -ChildPath $Path))
    if ($PSScriptRoot) {
        $candidates += (Join-Path -Path $PSScriptRoot -ChildPath $Path)
        $candidates += (Join-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -ChildPath $Path)
    }

    foreach ($candidate in $candidates) {
        if (Test-Path -Path $candidate) {
            return (Resolve-Path -Path $candidate).Path
        }
    }

    return $null
}

function Get-PortEntriesFromEnv {
    param([string]$Path)

    $resolvedPath = Resolve-EnvFilePath -Path $Path
    if (-not $resolvedPath) {
        throw "Env file not found: $Path"
    }

    $entries = @()
    foreach ($line in (Get-Content -Path $resolvedPath)) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }

        if ($trimmed -notmatch "^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$") {
            continue
        }

        $key = $matches[1]
        $value = $matches[2].Trim()
        if ($key -notmatch "(?i)(^|_)PORT($|_)") {
            continue
        }

        if (-not ($value.StartsWith("'") -or $value.StartsWith('"'))) {
            $hashIndex = $value.IndexOf("#")
            if ($hashIndex -ge 0) {
                $value = $value.Substring(0, $hashIndex).Trim()
            }
        }

        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            if ($value.Length -ge 2) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }

        if ($value -notmatch "^\d{1,5}$") {
            continue
        }

        $port = [int]$value
        if ($port -lt 1 -or $port -gt 65535) {
            continue
        }

        $entries += [PSCustomObject]@{
            Key  = $key
            Port = $port
        }
    }

    return [PSCustomObject]@{
        Path    = $resolvedPath
        Entries = $entries
    }
}

function Get-ListeningTcpPidMap {
    param([int[]]$TargetPorts)

    $map = @{}
    foreach ($line in (netstat -ano -p tcp)) {
        if ($line -notmatch "^\s*TCP\s+(\S+):(\d+)\s+(\S+)\s+(\S+)\s+(\d+)\s*$") {
            continue
        }

        $localPort = [int]$matches[2]
        $foreignAddress = $matches[3]
        $procId = [int]$matches[5]

        if ($TargetPorts -and ($TargetPorts -notcontains $localPort)) {
            continue
        }

        # Listening rows have a foreign endpoint ending in :0.
        if (-not $foreignAddress.EndsWith(":0")) {
            continue
        }

        if (-not $map.ContainsKey($localPort)) {
            $map[$localPort] = New-Object System.Collections.Generic.HashSet[int]
        }
        [void]$map[$localPort].Add($procId)
    }

    return $map
}

function Stop-ProcessTreeByPid {
    param([int]$ProcessId)

    $all = Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId
    $childrenMap = @{}
    foreach ($item in $all) {
        $parentKey = [int]$item.ParentProcessId
        if (-not $childrenMap.ContainsKey($parentKey)) {
            $childrenMap[$parentKey] = New-Object System.Collections.Generic.List[int]
        }
        $childrenMap[$parentKey].Add([int]$item.ProcessId)
    }

    $queue = New-Object System.Collections.Generic.Queue[int]
    $queue.Enqueue($ProcessId)
    $descendants = New-Object System.Collections.Generic.List[int]

    while ($queue.Count -gt 0) {
        $current = $queue.Dequeue()
        if (-not $childrenMap.ContainsKey($current)) {
            continue
        }
        foreach ($childPid in $childrenMap[$current]) {
            $descendants.Add($childPid) | Out-Null
            $queue.Enqueue($childPid)
        }
    }

    $rootExists = $null -ne (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
    if (-not $rootExists -and $descendants.Count -eq 0) {
        return [PSCustomObject]@{
            Success = $false
            Reason  = "not_found"
            Detail  = "Process $ProcessId is not running"
        }
    }

    foreach ($childPid in ($descendants | Sort-Object -Descending)) {
        try {
            Stop-Process -Id $childPid -Force -ErrorAction Stop
        }
        catch {
            # Ignore already-exited descendants.
        }
    }

    if (-not $rootExists) {
        return [PSCustomObject]@{
            Success = $true
            Reason  = "stopped"
            Detail  = "Stopped orphan descendants for missing PID $ProcessId"
        }
    }

    try {
        Stop-Process -Id $ProcessId -Force -ErrorAction Stop
        return [PSCustomObject]@{
            Success = $true
            Reason  = "stopped"
            Detail  = "Stopped process tree rooted at PID $ProcessId"
        }
    }
    catch {
        if ($_.Exception.Message -match "(?i)access is denied|拒绝访问") {
            return [PSCustomObject]@{
                Success = $false
                Reason  = "access_denied"
                Detail  = $_.Exception.Message
            }
        }
        return [PSCustomObject]@{
            Success = $false
            Reason  = "failed"
            Detail  = $_.Exception.Message
        }
    }
}

try {
    $envResult = Get-PortEntriesFromEnv -Path $EnvFile
    $resolvedEnvFile = $envResult.Path
    $portEntries = $envResult.Entries

    if (-not $portEntries -or $portEntries.Count -eq 0) {
        Write-Host "No PORT-like variables with numeric values found in ${resolvedEnvFile}."
        exit 0
    }

    $targetPorts = $portEntries | Select-Object -ExpandProperty Port -Unique | Sort-Object
    Write-Host "Ports from ${resolvedEnvFile}: $($targetPorts -join ', ')"

    for ($pass = 1; $pass -le $MaxPasses; $pass++) {
        $listenerMap = Get-ListeningTcpPidMap -TargetPorts $targetPorts
        $pidToPorts = @{}

        foreach ($port in $targetPorts) {
            if (-not $listenerMap.ContainsKey($port)) {
                if ($pass -eq 1) {
                    Write-Host "No listening TCP process on port $port."
                }
                continue
            }

            foreach ($procId in @($listenerMap[$port])) {
                if (-not $pidToPorts.ContainsKey($procId)) {
                    $pidToPorts[$procId] = New-Object System.Collections.Generic.HashSet[int]
                }
                [void]$pidToPorts[$procId].Add($port)
            }
        }

        if ($pidToPorts.Count -eq 0) {
            if ($pass -eq 1) {
                Write-Host "No matching listener processes found."
            } else {
                Write-Host "All matching listener processes are stopped."
            }
            exit 0
        }

        if ($pass -gt 1) {
            Write-Host "Retry pass $pass/$MaxPasses for remaining listeners..."
        }

        $stoppedAny = $false
        $hadAccessDenied = $false
        foreach ($procId in ($pidToPorts.Keys | Sort-Object)) {
            $ports = @($pidToPorts[$procId]) | Sort-Object
            $portsText = $ports -join ", "

            if ($DryRun) {
                Write-Host "[DryRun] Would stop PID $procId (ports: $portsText)"
                continue
            }

            $result = Stop-ProcessTreeByPid -ProcessId $procId
            if ($result.Success) {
                $stoppedAny = $true
                Write-Host "Stopped PID $procId (ports: $portsText)"
            } elseif ($result.Reason -eq "access_denied") {
                $hadAccessDenied = $true
                Write-Warning "Access denied for PID $procId (ports: $portsText). Try running this script as Administrator."
            } elseif ($result.Reason -eq "not_found") {
                Write-Host "PID $procId already exited (ports: $portsText)."
            } else {
                Write-Warning "Failed to stop PID $procId (ports: $portsText): $($result.Detail)"
            }
        }

        if ($DryRun) {
            exit 0
        }

        if ($hadAccessDenied -and -not $stoppedAny) {
            break
        }

        Start-Sleep -Milliseconds $RetryDelayMs
    }

    $remainingMap = Get-ListeningTcpPidMap -TargetPorts $targetPorts
    $remainingPorts = @()
    foreach ($port in $targetPorts) {
        if ($remainingMap.ContainsKey($port)) {
            $remainingPorts += $port
        }
    }

    if ($remainingPorts.Count -gt 0) {
        Write-Warning "Ports still listening after retries: $($remainingPorts -join ', ')"
        exit 2
    }

    Write-Host "All matching listener processes are stopped."
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
