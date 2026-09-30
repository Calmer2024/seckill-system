[CmdletBinding()]
param([switch]$Restore)

& (Join-Path $PSScriptRoot 'Invoke-ServiceChaos.ps1') -Service kafka -Restore:$Restore
