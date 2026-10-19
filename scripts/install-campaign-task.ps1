<#
Prepare a DISABLED daily task. Without -Install this only prints a preview.
Enabling it is a separate, explicitly authorized deployment step.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Python,
    [Parameter(Mandatory)][string]$Config,
    [string]$Repository = '',
    [string]$TaskName = 'Museum transcription campaign',
    [ValidatePattern('^\d{2}:\d{2}$')][string]$At = '20:00',
    [switch]$Install
)
$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($Repository)) {
    $Repository = Split-Path -Path $PSScriptRoot -Parent
}
$pythonPath = (Resolve-Path -LiteralPath $Python).Path
$configPath = (Resolve-Path -LiteralPath $Config).Path
$repoPath = (Resolve-Path -LiteralPath $Repository).Path
$workerPath = Join-Path $repoPath 'campaign.py'
if (-not (Test-Path -LiteralPath $workerPath -PathType Leaf)) { throw 'campaign.py is missing' }
$settingsData = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
if ($settingsData.worker_host -ne $env:COMPUTERNAME) { throw 'This is not the designated worker host' }
foreach ($value in @($pythonPath, $configPath, $workerPath)) {
    if ($value.Contains('"')) { throw 'Task paths may not contain quotes' }
}
$startTime = [datetime]::ParseExact($At, 'HH:mm', [Globalization.CultureInfo]::InvariantCulture)
$account = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$arguments = '"{0}" --config "{1}" run' -f $workerPath, $configPath
[pscustomobject]@{
    Name = $TaskName; Python = $pythonPath; Arguments = $arguments
    WorkingDirectory = $repoPath; LocalStartTime = $At; Account = $account
    Enabled = $false; AdditionalTrigger = 'User logon, delayed 5 minutes'
    Requirement = 'User signed in and Google Drive available; window may be locked'
} | Format-List
if (-not $Install) { return }
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    throw 'Task already exists; inspect it instead of overwriting it'
}
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument $arguments -WorkingDirectory $repoPath
$daily = New-ScheduledTaskTrigger -Daily -At $startTime
$logon = New-ScheduledTaskTrigger -AtLogOn -User $account
$logon.Delay = 'PT5M'
$principal = New-ScheduledTaskPrincipal -UserId $account -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -Disable -StartWhenAvailable -WakeToRun `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 20)
$task = New-ScheduledTask -Action $action -Trigger @($daily, $logon) -Principal $principal -Settings $settings `
    -Description 'Museum campaign: local durable progress; existing quota accounting; no automatic code updates.'
Register-ScheduledTask -TaskName $TaskName -InputObject $task | Out-Null
Write-Output 'Installed DISABLED. Review dry-run, quota migration, credentials and revision before explicitly enabling.'
