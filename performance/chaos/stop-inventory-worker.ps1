[CmdletBinding()]
param([switch]$Restore)

& (Join-Path $PSScriptRoot 'Invoke-ServiceChaos.ps1') -Service inventory_worker -Restore:$Restore
