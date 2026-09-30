[CmdletBinding()]
param(
    [int]$Port = 8099,
    [switch]$Background
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location $repoRoot

$healthUrl = "http://127.0.0.1:$Port/api/performance/health"
$serverPath = Join-Path $repoRoot 'performance/web/server.py'

try {
    $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
    if ($health.status -eq 'ok') {
        Write-Host "Performance web controller is already running at http://127.0.0.1:$Port"
        exit 0
    }
} catch {
    # The controller is not running yet.
}

if ($Background) {
    $pythonw = Get-Command pythonw -ErrorAction SilentlyContinue
    $launcher = if ($pythonw) { $pythonw.Source } else { (Get-Command python -ErrorAction Stop).Source }
    Start-Process -FilePath $launcher `
        -ArgumentList @($serverPath, '--host', '127.0.0.1', '--port', "$Port") `
        -WorkingDirectory $repoRoot `
        -WindowStyle Hidden | Out-Null

    for ($attempt = 0; $attempt -lt 20; $attempt += 1) {
        Start-Sleep -Milliseconds 250
        try {
            $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
            if ($health.status -eq 'ok') {
                Write-Host "Performance web controller started in background at http://127.0.0.1:$Port"
                exit 0
            }
        } catch {
            # Keep waiting for the process to bind its port.
        }
    }

    throw "Performance web controller did not become healthy at $healthUrl"
}

Write-Host "Starting performance web controller on http://127.0.0.1:$Port ..."
python $serverPath --host 127.0.0.1 --port $Port
