[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('kafka', 'order_worker', 'inventory_worker', 'product_service_1', 'product_service_2')]
    [string]$Service,
    [switch]$Restore
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $repoRoot

if ($Restore) {
    & docker compose start $Service
} else {
    & docker compose stop $Service
}

if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose operation failed for service '$Service'."
}

if ($Restore) {
    Write-Host "Restored $Service."
} else {
    Write-Host "Stopped $Service. Run this command with -Restore to start it again."
}
