<#
.SYNOPSIS
Find evidence of nests, birds and skins in saved egg-slip transcriptions.
#>
[CmdletBinding()]
param(
    [string]$FamilyRoot = 'G:\My Drive\Egg Slip Scanning\Family',
    [string]$OutputFile = (Join-Path (Get-Location) ('Egg-Slip-Associated-Specimens-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.xlsx')),
    [string]$Python = 'python'
)

$ErrorActionPreference = 'Stop'
$root = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($FamilyRoot)
$destination = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputFile)
& $Python (Join-Path $PSScriptRoot 'find_associated_specimens.py') $root $destination
if ($LASTEXITCODE -ne 0) { throw "The specimen search exited with code $LASTEXITCODE." }
