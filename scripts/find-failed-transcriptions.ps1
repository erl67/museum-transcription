<#
List latest failed results and special fresh checks needing a normal viewer report.
Reports and scans are read only. No transcription requests are made.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$FamilyRoot,
    [string]$OutputFile = (Join-Path (Get-Location) 'Status-Failed.txt')
)
$ErrorActionPreference = 'Stop'
$root = Get-Item -LiteralPath $FamilyRoot
if (-not $root.PSIsContainer) { throw 'FamilyRoot must be the directory containing the family folders.' }
$destination = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputFile)
if ([IO.Path]::GetFileName($destination) -match '_transcriptions_|_\d{8}_\d{4}') {
    throw 'OutputFile must not overwrite a transcription report or journal.'
}

$families = @(Get-ChildItem -LiteralPath $root.FullName -Directory | Sort-Object Name)
$activity = 'Finding saved transcription reports'
try {
    $reports = @(
        for ($i = 0; $i -lt $families.Count; $i++) {
            $family = $families[$i]
            Write-Progress -Activity $activity -Status "$($i + 1)/$($families.Count): $($family.Name)" -PercentComplete (100 * $i / $families.Count)
            foreach ($file in Get-ChildItem -LiteralPath $family.FullName -File -Filter '*.txt') {
                if ($file.FullName -eq $destination) { continue }
                # Normal species reports and individual E-number reports; not combined tests.
                if ($file.Name -notmatch '_transcriptions_|^E\d+_') { continue }
                if ($file.Name -notmatch '^(?<stem>.+)_(?<stamp>\d{8}_\d{4})(?:_(?<suffix>.+))?\.txt$') {
                    throw "Unrecognized report filename: $($file.FullName)"
                }
                $stamp = [datetime]::ParseExact($Matches.stamp, 'yyyyMMdd_HHmm', [Globalization.CultureInfo]::InvariantCulture)
                $sequence = 1
                if ($Matches.suffix -match '^(\d+)(?:_|$)') { $sequence = [int]$Matches[1] }
                $target = ''
                if ($file.Name -match '^(E\d+)_') { $target = $Matches[1] }
                [pscustomobject]@{ File = $file; Stamp = $stamp; Sequence = $sequence; Target = $target }
            }
        }
    )
} finally {
    Write-Progress -Activity $activity -Completed
}
if ($reports.Count -eq 0) { throw "No dated transcription reports found in family subfolders of $($root.FullName)" }
$reports = @($reports | Sort-Object -Property Stamp, Sequence, @{Expression={$_.File.LastWriteTimeUtc}},
    @{Expression={$_.File.FullName}} -Descending)
$latest = @{}
$activity = 'Checking latest card results'
try {
    for ($i = 0; $i -lt $reports.Count; $i++) {
        $report = $reports[$i]
        Write-Progress -Activity $activity -Status "$($i + 1)/$($reports.Count): $($report.File.Name)" -PercentComplete (100 * $i / $reports.Count)
        $content = Get-Content -LiteralPath $report.File.FullName -Raw -Encoding UTF8
        if ($null -eq $content) { $content = '' }
        # A status belongs to the preceding card ID, not a standalone line in source text.
        $cards = [regex]::Matches($content, '(?m)^ID: (?<id>[^\r\n]+)\r?\nSTATUS: (?<status>[^\r\n]+)\r?$')
        for ($j = $cards.Count - 1; $j -ge 0; $j--) {
            $card = $cards[$j]
            $identity = $card.Groups['id'].Value.Trim()
            $key = $report.File.DirectoryName + '|' + $identity
            if ($latest.ContainsKey($key)) { continue }
            $status = $card.Groups['status'].Value.Trim() -replace '\s+\(reused\)$', ''
            if ($status -notmatch '^(OK|REVIEW|FAILED|PAUSED)$') {
                throw "Unrecognized status for $identity in $($report.File.FullName): $status"
            }
            $end = $content.Length
            if ($j + 1 -lt $cards.Count) { $end = $cards[$j + 1].Index }
            $block = $content.Substring($card.Index, $end - $card.Index)
            $errorLine = [regex]::Match($block, '(?m)^={50}\r?\nERROR: ([^\r\n]*)')
            $reason = $errorLine.Groups[1].Value.Trim()
            if (-not $reason) { $reason = 'No ERROR line recorded; inspect the source report.' }
            $latest[$key] = [pscustomobject]@{ ID = $identity; Status = $status; Reason = $reason;
                Report = $report.File.FullName; Target = $report.Target }
        }
    }
} finally {
    Write-Progress -Activity $activity -Completed
}
$failures = @($latest.Values | Where-Object Status -EQ 'FAILED' | Sort-Object Report, ID)
$specialChecks = @($latest.Values | Where-Object { $_.Target })
$followUp = @($latest.Values | Where-Object { $_.Status -eq 'FAILED' -or $_.Target } | Sort-Object Report, ID)

$lines = [Collections.Generic.List[string]]::new()
$lines.Add("$($failures.Count) failed card(s); checked $($latest.Count) card(s) across $($reports.Count) saved reports.")
if ($specialChecks.Count) {
    $lines.Add("$($specialChecks.Count) latest special-check result(s) need a normal viewer report (may overlap failures).")
}
$lines.Add('Generated: ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'))
$lines.Add('Latest result per card: failures and special checks only. RUN commands request fresh normal reports; nothing is run automatically.')
$lines.Add('')
foreach ($card in $followUp) {
    $lines.Add('ID: ' + $card.ID)
    $lines.Add('STATUS: ' + $card.Status.ToUpperInvariant())
    if ($card.Status -in @('FAILED', 'PAUSED')) { $lines.Add('ERROR: ' + $card.Reason) }
    if ($card.Target) {
        $lines.Add('NOTE: Special fresh check; the viewer ignores this report. An older normal result may still be available.')
        $lines.Add('RUN: python transcribe.py ' + $card.Target + ' --force')
    }
    $lines.Add('Report: ' + $card.Report)
    $lines.Add('')
}
$lines | Set-Content -LiteralPath $destination -Encoding UTF8
$lines
Write-Host "Saved: $destination"
