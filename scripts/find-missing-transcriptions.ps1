<#
.SYNOPSIS
Compare catalogue E-numbers with saved transcriptions in their family folders.
.DESCRIPTION
List catalogue numbers that still need follow-up. Omit CSV-only records
when a saved (MISSING) block contains catalogue data.
Keep the latest failure or other incomplete result as evidence for each gap.
The catalogue and Family tree are read only. No transcription requests are made.
#>
[CmdletBinding()]
param(
    [string]$FamilyRoot = 'G:\My Drive\Egg Slip Scanning\Family',
    [string]$CsvPath = 'G:\My Drive\Egg Slip Scanning\EggSlipReorganizationProject_FULL.xlsx - Full List.csv',
    [string]$OutputFile = (Join-Path $PSScriptRoot 'Status-Transcription-Coverage.txt')
)

$ErrorActionPreference = 'Stop'
$root = Get-Item -LiteralPath $FamilyRoot
$csv = Get-Item -LiteralPath $CsvPath
if (-not $root.PSIsContainer -or $csv.PSIsContainer) {
    throw 'FamilyRoot must be a directory and CsvPath must be a CSV file.'
}
$destination = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputFile)
$rootPrefix = $root.FullName.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
if ($destination -eq $csv.FullName -or
    $destination.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase) -or
    [IO.Path]::GetFileName($destination) -match '_transcriptions_|_\d{8}_\d{4}') {
    throw 'Choose an output file outside the Family tree, separate from the catalogue and transcription reports.'
}

# Import-Csv assigns a placeholder to the production export's blank Case header.
$rows = @(Import-Csv -LiteralPath $csv.FullName -Encoding UTF8 -WarningAction SilentlyContinue)
if (-not $rows.Count) { throw "The catalogue has no data rows: $($csv.FullName)" }
$columns = @{}
foreach ($property in $rows[0].PSObject.Properties) { $columns[$property.Name.Trim()] = $property.Name }
foreach ($name in @('catalogNumber', 'Scientific Name', 'Family')) {
    if (-not $columns.ContainsKey($name)) { throw "Missing catalogue column: $name" }
}

$catalogue = @{}
foreach ($row in $rows) {
    $number = ([string]$row.($columns['catalogNumber'])).Trim().ToUpperInvariant()
    if (-not $number) { continue }
    if ($number -notmatch '^E[0-9]+$') { throw "Expected an E-number in the catalogue, found '$number'." }
    $family = ([string]$row.($columns['Family'])).Trim()
    $key = "$family|$number"
    if ($catalogue.ContainsKey($key)) { continue }
    $name = [string]$row.($columns['Scientific Name'])
    $parts = $name.Replace('_', ' ').Trim() -split '\s+'
    $identity = $number
    if ($parts.Count -ge 2) {
        $genus = $parts[0].Substring(0, 1).ToUpperInvariant() + $parts[0].Substring(1).ToLowerInvariant()
        $identity = $genus + '_' + $parts[1].ToLowerInvariant().TrimEnd('.') + "_$number"
    }
    $catalogue[$key] = [pscustomobject]@{ Number = $number; Family = $family; ID = $identity;
        Complete = $false; Incomplete = $null; HasCsvData = $false }
}
if (-not $catalogue.Count) { throw "No E-numbers found in $($csv.FullName)" }

$families = @(Get-ChildItem -LiteralPath $root.FullName -Directory)
$familyNames = @{}
$activity = 'Finding family transcription reports'
try {
    $reports = @(
        for ($i = 0; $i -lt $families.Count; $i++) {
            $family = $families[$i]
            $familyNames[$family.Name] = $true
            Write-Progress -Activity $activity -Status "$($i + 1)/$($families.Count): $($family.Name)" -PercentComplete (100 * $i / $families.Count)
            foreach ($file in Get-ChildItem -LiteralPath $family.FullName -File -Filter '*.txt') {
                if ($file.Name -notmatch '_transcriptions_|^E[0-9]+_') { continue }
                if ($file.Name -notmatch '^.+_(?<stamp>[0-9]{8}_[0-9]{4})(?:_(?<suffix>.+))?\.txt$') {
                    throw "Unrecognized report filename: $($file.FullName)"
                }
                $stamp = [datetime]::ParseExact($Matches.stamp, 'yyyyMMdd_HHmm', [Globalization.CultureInfo]::InvariantCulture)
                $sequence = 1
                if ($Matches.suffix -match '^([0-9]+)(?:_|$)') { $sequence = [int]$Matches[1] }
                [pscustomobject]@{ File = $file; Family = $family.Name; Stamp = $stamp; Sequence = $sequence }
            }
        }
    )
} finally {
    Write-Progress -Activity $activity -Completed
}
if (-not $reports.Count) { throw "No dated transcription reports found in family subfolders of $($root.FullName)" }
$reports = @($reports | Sort-Object -Property Stamp, Sequence, @{Expression={$_.File.LastWriteTimeUtc}},
    @{Expression={$_.File.FullName}} -Descending)

$activity = 'Checking saved transcription coverage'
$bannerPattern = [regex]'(?m)^={22}(?<label>[^=\n][^\n]*?)={2,}$'
$headerPattern = [regex]'\A\nID: (?<id>[^\n]+)\nSTATUS: (?<status>OK|REVIEW|FAILED|PAUSED)(?: \(reused\))?(?=\n|\z)'
$separator = "`n" + ('=' * 50) + "`n"
$footerPattern = '\n{3}(?:SAVED RESULT USAGE \(includes recorded retries; not new spending this run\):\n)?TOKENS: [^\n]*\nAVERAGE/CALL[^\n]*\nRUN: [^\n]*\n*\z'
try {
    for ($i = 0; $i -lt $reports.Count; $i++) {
        $report = $reports[$i]
        Write-Progress -Activity $activity -Status "$($i + 1)/$($reports.Count): $($report.File.Name)" -PercentComplete (100 * $i / $reports.Count)
        $content = Get-Content -LiteralPath $report.File.FullName -Raw -Encoding UTF8
        if ([string]::IsNullOrEmpty($content)) { continue }
        $content = $content.Replace("`r`n", "`n")
        $content = $content -creplace $footerPattern, "`n`n`n"
        $banners = $bannerPattern.Matches($content)
        # Read backwards so the last result in a file wins ties for diagnostic evidence.
        $end = $content.Length
        for ($j = $banners.Count - 1; $j -ge 0; $j--) {
            $banner = $banners[$j]
            $start = $banner.Index + $banner.Length
            $block = $content.Substring($start, $end - $start)
            $end = $banner.Index
            $label = $banner.Groups['label'].Value
            if ($label -cmatch '^CM([0-9]+) \(MISSING\)$') {
                $entry = $catalogue["$($report.Family)|E$($Matches[1])"]
                if ($entry -and $block.EndsWith("`n`n`n") -and $block -cmatch '(?m)^[^\s:\n][^:\n]*: +\S') {
                    $entry.HasCsvData = $true
                }
                continue
            }
            if ($label -cnotmatch '^CM([0-9]+)$') { continue }
            $numbers = @('E' + $Matches[1])
            # A shared slip has consecutive CM banners above the same ID and body.
            while ($j -gt 0) {
                $previous = $banners[$j - 1]
                if ($end -ne ($previous.Index + $previous.Length + 1) -or
                    $previous.Groups['label'].Value -cnotmatch '^CM([0-9]+)$') { break }
                $numbers += 'E' + $Matches[1]
                $j--
                $end = $previous.Index
            }
            $entries = @(foreach ($number in $numbers) {
                $entry = $catalogue["$($report.Family)|$number"]
                if ($entry -and -not $entry.Complete) { $entry }
            })
            if (-not $entries.Count) { continue }

            $header = $headerPattern.Match($block)
            $identity = $header.Groups['id'].Value.Trim()
            $status = $header.Groups['status'].Value
            $bodyStart = $block.IndexOf($separator, [StringComparison]::Ordinal)
            $body = if ($bodyStart -ge 0) { $block.Substring($bodyStart + $separator.Length) } else { '' }
            if ($status -in @('OK', 'REVIEW') -and $body.Trim() -and
                $body.EndsWith("`n`n`n") -and $body -cnotmatch '\AERROR: ') {
                foreach ($entry in $entries) { $entry.Complete = $true }
                continue
            }
            $reason = 'Saved transcription block is empty or incomplete.'
            if ($status -in @('FAILED', 'PAUSED')) {
                $reason = 'No ERROR line recorded; inspect the source report.'
                if ($body -cmatch '\AERROR: ([^\n]+)') { $reason = $Matches[1].Trim() }
            } else {
                $status = 'INCOMPLETE'
            }
            foreach ($entry in $entries) {
                if (-not $entry.Incomplete) {
                    $entry.Incomplete = [pscustomobject]@{ ID = $identity; Status = $status;
                        Reason = $reason; Report = $report.File.FullName }
                }
            }
        }
    }
} finally {
    Write-Progress -Activity $activity -Completed
}

$gaps = @($catalogue.Values | Where-Object { -not $_.Complete })
$followUp = @($gaps | Where-Object { $_.Incomplete -or -not $_.HasCsvData } |
    Sort-Object Family, @{Expression={ $_.Number.Length }}, Number)
$incomplete = @($followUp | Where-Object { $_.Incomplete }).Count
$csvOnly = $gaps.Count - $followUp.Count
$noResult = $followUp.Count - $incomplete
$lines = [Collections.Generic.List[string]]::new()
$lines.Add("$($catalogue.Count - $gaps.Count) of $($catalogue.Count) catalogue E-number/family pairs have a saved transcription across $($reports.Count) reports.")
$lines.Add("$csvOnly CSV-only record(s) omitted because their (MISSING) blocks contain catalogue data.")
$lines.Add("$($followUp.Count) to follow up ($incomplete failed, paused, or incomplete; $noResult without a saved result or populated (MISSING) block).")
$lines.Add('Generated: ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'))
$lines.Add('Catalogue: ' + $csv.FullName)
$lines.Add('Family root: ' + $root.FullName)
$lines.Add('')
foreach ($entry in $followUp) {
    $result = $entry.Incomplete
    $identity = if ($result -and $result.ID) { $result.ID } else { $entry.ID }
    $lines.Add('ID: ' + $identity)
    $lines.Add('E-number: ' + $entry.Number)
    if ($result) {
        $lines.Add('STATUS: ' + $result.Status)
        $lines.Add('ERROR: ' + $result.Reason)
        $lines.Add('Report: ' + $result.Report)
    } else {
        $lines.Add('STATUS: NO TRANSCRIPTION')
        $lines.Add('ERROR: NO TRANSCRIPTION FOUND')
    }
    $lines.Add('Family: ' + $entry.Family)
    if (-not $familyNames.ContainsKey($entry.Family)) { $lines.Add('NOTE: Catalogue family folder not found.') }
    $lines.Add('')
}
$lines | Set-Content -LiteralPath $destination -Encoding UTF8
$lines
Write-Host "Saved: $destination"
