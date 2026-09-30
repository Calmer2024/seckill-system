[CmdletBinding()]
param(
    [ValidateSet(1, 2)]
    [int]$Instance = 1,
    [switch]$Restore
)

& (Join-Path $PSScriptRoot 'Invoke-ServiceChaos.ps1') `
    -Service "product_service_$Instance" `
    -Restore:$Restore
