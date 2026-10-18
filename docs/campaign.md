# Unattended transcription campaigns

`campaign.py` runs a sequential egg-slip campaign independently of Codex and VS Code. It uses the existing transcription engine and preserves the chosen Gemini profile, reading instructions, side grouping, validation, and report blocks. Interactive `transcribe.py` retains its **48-hour** cache policy. Campaign completion has no age expiry. Structural `OK` is not human verification; accepted `REVIEW` cards are complete for automatic processing and still require collection review.

No production campaign or scheduled task was enabled during development. Review the offline dry run, code, machine paths, and quota migration before authorizing live work.

## Storage and recovery

Keep the checkout, virtual environment, campaign state, quota file, and fallback storage on the home desktop's **local unsynchronized disk**. Source scans, the CSV, and readable reports may remain in Drive. Known sync-folder names and non-fixed Windows disks are rejected for transactional state; custom sync software must also exclude these locations.

The SQLite store uses full synchronous transactions. It contains a physical-card queue, append-only result history, request reservation records, publication locations, and operational status. A separate SQLite write lock associated with the quota path excludes workers across Windows logon sessions and releases automatically after a crash. Leftover lock files are harmless; do not delete lock databases while a worker is running. This is a single-machine lock, **not a distributed Drive lock**. Use one quota path for all campaigns on this computer. Do not run the interactive engine concurrently: its existing per-species locks do not cover an entire campaign request.

Every response is committed locally before readable output. Per-species report snapshots and compatible journals are published at startup (recovery) and at the end of each invocation. A crash during a batch can therefore leave completed results in SQLite until the next invocation or `reconcile`. Existing reports are never overwritten. New report names use the established `<species>_transcriptions_YYYYMMDD_HHMM[_counter].txt` convention in the family directory; journals use `<species>_transcriptions_cache.jsonl`. Reports contain all currently saved, non-stale results for that species and refreshed CSV-only missing blocks. Pending unattempted cards are not presented as transcribed. Snapshot footers summarize the recorded usage of included results, not spending during the publication operation; older imported records can lack usage. Full campaign attempt totals are in `status`.

Queue identity combines family, species, and the grouped physical-card base ID. Fingerprints additionally bind ordered relative filenames, sections, raw file hashes, full relevant catalogue rows, and the engine's existing request fingerprint (prepared image content, prompt, hints and generation settings). Every scan recalculates fingerprints and revalidates completed text with the current validator. Immediately before a request, the worker checks side grouping, image hashes, catalogue context and approved runtime files again. Changed or removed cards become `stale`; possible renaming within a species also holds new identities for review. Historical results remain in `history`. Moving a card to another family/species is a manual migration concern: pause and reconcile identities before processing reorganized inputs.

Valid matching journals may be imported read-only even when older than 48 hours, including checkpoints saved manually after queue creation. Import requires the actual request key, completed status, usable warnings/text, compatible cache version and current structural validation. A report file is never completion evidence. Explicit refresh bypasses checkpoint import. Imported work does not count as new campaign API spending. Uncatalogued-only species in either supported folder layout are discovered; `extra_species` can supply an explicit species-to-family mapping when needed. Ambiguous directories and rejected scans stop discovery rather than becoming invented missing-card records.

## Configure this computer

1. Keep a local clone, with a tested, deliberately deployed revision. Create `.venv` and install `docs/requirements.txt`.
2. Copy [campaign.example.json](campaign.example.json) to an ignored `campaign.local.json` or a private directory. Use absolute paths. Replace `worker_host` with the result of `$env:COMPUTERNAME`. Default model: `gemini-3.5-flash-lite`, temperature 1.0, high thinking, original resolution, 15 RPM / 500 daily attempts. The worker uses model-profile defaults and accepts only the documented configuration fields; it rejects an uncapped daily allowance.
3. Set `csv` explicitly; this local clone need not contain the catalogue. Set `env_file` to a private `.env`, or omit it to retain the engine's normal `.env` lookup. Never include a key in JSON, task arguments or Git. Credentials are loaded only when an actual request is needed.
4. Set `state_dir` and `quota_file` outside Drive. `log_file` defaults to `state_dir/campaign.log`. Optional `status_file` exports a JSON summary, and may be placed on Drive for the other computer. It contains card IDs, paths and operational statistics; treat it as collection data. Its parent must exist. For reliable fallback operation keep status local when Drive may disappear.

### Preserve existing quota history before deployment

Stop all production writers on both computers first. The local clone has no history merely because the old Drive installation does. Copy the existing file **once**, without overwriting either source or an existing destination:

```powershell
$python = '.\.venv\Scripts\python.exe'
$cfg = 'C:\MuseumCampaign\campaign.local.json'
& $python campaign.py --config $cfg init --quota-source 'G:\My Drive\Egg Slip Scanning\Transcription\transcribe_request_usage.json'
```

`init` validates and preserves every model entry and original bytes, pins the runtime file hashes and configured locations, and creates local state. It makes no API calls. An existing destination is an error rather than a reset or overwrite. If already using a validated local quota file, omit `--quota-source`. Initialization refuses to invent an empty quota history. A damaged counter, deleted counter, unsupported campaign schema or changed bound locations stops execution. Keep a backup of the original history. Do not resume writes to the old file after copying it: that creates diverging counts. Point authorized interactive runs to the same local `--quota-file`, and coordinate any laptop requests explicitly.

The existing `DailyQuota` reserves **every attempt before transmission**, including service and formatting retries. Campaign intent records precede that reservation. If a crash leaves uncertainty about whether quota was saved, recovery adds a conservative reservation for the same quota day (possibly double-counting one ambiguous attempt, never knowingly undercounting). An interrupted card is retried no earlier than the next quota day. A reservation does not prove a request reached the service; status reports uncertain attempts separately. Unknown tokens/costs stay unknown.

Gemini accounting resets at midnight in **America/Los_Angeles**, with daylight-saving rules. It is not local midnight on the Eastern-time desktop. Provider-reported daily exhaustion is also retained by the existing counter. Exhausted runs send nothing further. Service retries remain bounded by the existing per-card policy, with at most `retry_days` failed sessions per card (default three) before intervention. There is no overnight wait or continuous restart loop. Authentication/model/billing failures create the pause marker and stop the batch. `resume` clears the pause, but permanent failures also require explicit `retry` after correcting their cause.

## Offline inspection and controls

```powershell
& $python campaign.py --config $cfg dry-run
& $python campaign.py --config $cfg scan
& $python campaign.py --config $cfg status
& $python campaign.py --config $cfg pause
& $python campaign.py --config $cfg resume
& $python campaign.py --config $cfg retry --card 'birds/test_bird/test_bird_e01'
& $python campaign.py --config $cfg refresh --card 'birds/test_bird/test_bird_e01'
& $python campaign.py --config $cfg reconcile
```

- `dry-run` is read-only: routing, grouping, decoding and hashes, no credentials, state creation or API. It reads every eligible image, so a full streamed Drive collection can take time. For a quick filename-only check first use the existing `transcribe.py "2-20000" --csv ... --base-dir ... --dry-run` (choose an end row covering your CSV).
- `scan` updates the local queue and imports safe checkpoints; it sends no requests and writes no collection reports. Discovery errors preserve the previous queue, record the issues and stop processing. Correct input availability/routing before retrying.
- `status` reads only, without creating/resetting quota or contacting a model. It reports cards/images, completion/review/failures/staleness, missing CSV row counts, daily and campaign attempts, tokens/costs, locations, last family/species/card, last successful invocation, errors, and processing-day estimates. Estimates use observed attempts per new completion, with a lower bound of one attempt per remaining card; they exclude unresolved stale/permanent failures and are not a promised finish date. Imported-only work supplies no observed rate.
- `pause` can run while a worker is active. An in-flight request may finish and is checkpointed; the next attempt sees the marker. `resume`, `retry`, `refresh`, `scan`, `reconcile` and `accept-code` require the worker lock.
- `retry` selects exactly one retryable/permanent failure. `refresh` deliberately queues one active completed/review/stale card, preserves its history and bypasses old-checkpoint reuse. Neither command sends a request. Use IDs from `dry-run` or `cards_requiring_attention` in status. Removed source cards cannot be refreshed until restored and rescanned.
- `reconcile` renders saved work and copies/verifies pending outputs without requests. Back up the **entire state directory**, including artifacts, only when the worker is stopped; retain the quota file as well. Never synchronize the live database or use a stale backup to lower current quota counts.

Queue states are `pending`, `in_progress`, `completed`, `review`, `retryable`, `permanent`, and `stale`. Missing-source catalogue entries are stored separately, with duplicate rows preserved, and rendered only as CSV-derived `(MISSING)` blocks. Engine result statuses remain `OK`, `REVIEW`, `FAILED`, and `PAUSED`; the queue does not redefine them.

## Drive availability and fallback

`output_policy: "stop"` is the default. Output roots/family directories must already exist and pass a write/fsync probe before requests. Source root, CSV and all required image groups must also be readable. This prevents a disconnected drive from being recreated accidentally as an empty collection.

`output_policy: "fallback"` requires a local `fallback_dir`. When output storage is unavailable but inputs remain readable, the worker may proceed, retaining SQLite checkpoints and writing the same journals/reports under `fallback_dir/<family>/`. It cannot transcribe images that are themselves unavailable; no scan mirroring/downloading subsystem is provided. Status lists the exact immutable local artifact, fallback path, intended Drive path and publication state.

Run `reconcile` after Drive returns. Journals are appended using result IDs; reports use exclusive names and content-hash read-back verification. Repeated reconciliation is idempotent. Missing published files can be restored from immutable local artifacts; conflicting or edited reports are retained and require intervention. A fully written temporary file is linked into place where supported; Drive filesystems without hard links use exclusive creation. If interrupted during that fallback copy, a partial/conflicting destination is preserved for review rather than overwritten: move that **generated** partial aside after checking it, then reconcile again. Source scans and CSV data are never edited.

`drive_local` means bytes were read back from the mounted filesystem. **It never means Google confirmed remote upload.** `remote_upload_verified` remains false. Verify Drive sync through Drive before relying on the remote copy or retiring local state/artifacts; no automated remote-upload attestation is implemented.

## Windows scheduling — review before enabling

The helper previews by default; `-Install` registers a **disabled** task and refuses to overwrite an existing task. It uses the selected Python executable, absolute config/script paths, a daily trigger, a five-minute delayed user-logon trigger, missed-start recovery, wake request and `IgnoreNew` overlap handling. Execution is bounded to 20 hours, with no automatic failure-restart loop. These settings use Microsoft's [ScheduledTasks settings](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/new-scheduledtasksettingsset) and [interactive principal](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/new-scheduledtaskprincipal).

```powershell
.\scripts\install-campaign-task.ps1 -Python "$PWD\.venv\Scripts\python.exe" -Config $cfg -At '20:00'
# Only after reviewing the preview:
.\scripts\install-campaign-task.ps1 -Python "$PWD\.venv\Scripts\python.exe" -Config $cfg -At '20:00' -Install
```

The default is **20:00 (8 p.m.) Windows local time**, as requested for the Eastern-time home desktop. This changes the launch time; quota still resets at Pacific midnight. Requests made at work earlier in that quota day can reduce the provider allowance available that evening. Local counters do not automatically synchronize across computers. A recognized provider daily-quota error stops the worker and preserves progress until a later invocation. A combined, self-imposed 500-attempt ceiling across computers additionally requires coordinating counts; two independent local caps do not enforce one shared cap. The interactive principal needs the user signed in (locking the screen is fine) and Drive running. After reboot, the logon trigger resumes once the user signs in. The helper does not configure Windows automatic sign-in, start Drive under another account, store a Windows password, or claim access to an absent user-session mount. A completely signed-out deployment would need independently accessible local inputs/output staging and a separately reviewed service-account task.

After enabling the installed task, use **Task Scheduler Library > Museum transcription campaign > Run** to start early, or `Start-ScheduledTask -TaskName 'Museum transcription campaign'`. An early start retains the daily trigger, completion tracking and quota limits. The worker lock prevents overlap with another campaign invocation; a separate scan also holds that lock, so wait for it to finish. Reaching quota stops the current invocation; the next automatic daily start is at 20:00, rather than immediately at the quota reset.

Only after separate authorization to spend production quota:

```powershell
# A manual live invocation, if specifically authorized:
& $python campaign.py --config $cfg run
# Enable the reviewed task only when production scheduling is authorized:
Enable-ScheduledTask -TaskName 'Museum transcription campaign'
```

Task Scheduler exit results: `0` completed current eligible work; `10` daily quota pause; `11` operator pause; `12` bounded service retry deferred; `20` intervention/configuration/stale/permanent/discovery/lock issue; `21` storage unavailable; `130` manual interruption. A completed campaign with unread human-review flags still returns 0. Read the persistent log and JSON status for detail. A Drive-only status destination can itself fail; the local database and log remain authoritative.

## Code updates and two-computer coordination

Develop on `feature/unattended-transcription`, not directly on main. Before switching revisions, pause the worker, wait for its process to exit, back up state, inspect Git status and remote changes, and run both offline suites. Do not pull code while a worker is active. Resolve laptop changes deliberately; do not reset/rebase over local work or force-push.

Deploy a tested revision and run `accept-code` to record the current four runtime file hashes. This is an offline operator acknowledgement, not a test runner. The next scan still detects prompt, source, catalogue or generation changes and marks affected results stale; code approval does not automatically refresh them. Compatible updates retain durable completion. Schema version mismatches require a deliberate migration; never delete the database as an upgrade procedure. Keep generation-policy changes separate from automation fixes.

Offline verification:

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_transcribe.py test_campaign.py
```

All campaign tests use generated images, temporary files, simulated days and the existing fake client. No model service is called. Hardware power recovery, actual mounted-Drive atomicity and remote sync, real credential validity, and enabled Task Scheduler execution remain deployment checks.
