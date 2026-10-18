# Home desktop automation handoff — 12 October 2026

Branch: `feature/unattended-transcription`. Starting commit:
`ea9830bbf6c3129f6c0a607f2a4d4bc2ae35624d` (`docs`). Local main, GitHub main and
the remote feature branch matched that commit at inspection. The checkout was clean
and already independent of Drive. No relocation, destructive Git action, merge,
production quota migration, live transcription or scheduled task activation occurred.
Use `git log -1` for the final handoff commit and `git status -sb` for unpushed work;
a commit cannot contain its own SHA.

Implementation commit: `44792a0` — `Add durable unattended transcription campaign worker`.
The following documentation commit contains this handoff. Both commits remain local;
no push or merge was performed. GitHub main and the remote feature branch were checked
again after implementation and still pointed to the starting SHA.

## Delivered and changed files

**18 October 2026 acknowledged unavailable sources:** The maintainer confirmed the
13 unresolved species folders have no available scans and cannot be fixed. The
campaign now accepts `skip_missing_species`, an explicit mapping of exact species
names to nonempty reasons in private configuration. Only a typed missing-JPEG-folder
error for a listed species is non-blocking. Unknown missing species, ambiguous
layouts, missing family/root storage, access errors and rejected filenames remain
blocking. Scans supplied later are included automatically. Skipped species and their
catalogue-row counts remain separate in CLI/JSON status; they are not transcribed,
not counted complete and not converted into CSV-only `(MISSING)` blocks.

The engine only gains the egg-specific `MissingJPEGDirectory(ValueError)` subtype
with the existing error text. No prompts, request/cache fingerprints, validation,
providers or quota behavior changed. `campaign.inventory` now returns an additional
fifth value for acknowledged unavailable species. No database schema migration is
needed. A successful scan clears previous discovery errors while preserving a pause.

Baseline: **215 tests, 214 passed, one optional fixture skip**. Final offline suite:
**225 tests, 224 passed, the same skip**, including both mocked provider transports.
Ten new cases cover explicit source-gap acknowledgement, separate status and duplicate
row counts, available-card processing, future scan arrival, invalid configuration,
strict handling of ambiguity/names/access/root failures and clearing resolved errors.
No live requests are part of these checks. Apply private configuration changes under
the worker lock after backing up settings/state and preserving all quota history.

Applied code commit `87d3776` locally. Settings, database and quota history were backed
up under the ignored `private/unavailable-species-2026-10-18-ad4edec3` directory before
adding the 13 confirmed species and approving the tested runtime. The actual offline
scan succeeded in **132.3 seconds**: **10,015 groups / 11,496 images, zero discovery
issues, 13 acknowledged unavailable species**, and **10,015 pending queue cards**.
Quota-file bytes were unchanged. The task was not enabled and no transcription was
started. The short local naming checklist now distinguishes these acknowledged source
gaps from errors rather than telling staff to repair empty folders.

**18 October 2026 fast-scan update:** The maintainer confirmed the JPG collection
is expected to remain stable and requested replacing the expensive repeated full
scan. Routine `scan`, `dry-run` and worker discovery now inspect names, grouping,
sizes, modification times and filesystem identity, plus prompt/settings/catalogue
context. They display per-species progress and do not open JPG contents. The explicit
`verify` command reads all images once and compares compatible content fingerprints.
Changes that preserve all checked metadata require this explicit content audit.

Code commit: `ccc0dbe` (`Make campaign scans metadata-only with lazy image verification`).
The pre-existing local database and quota file were backed up under the ignored
`private/campaign-upgrade-2026-10-18-abb6c1af` directory before applying the upgrade.
The database had zero queue records and zero historical results; its schema was
upgraded and the tested runtime approved with the existing offline `accept-code`
command. The scheduled task remained disabled. The normal CLI scan was then run
to record the remaining discovery issues; quota bytes were checked unchanged.

The worker prepares selected cards from a single read of each image and checks for
metadata changes during preparation. `transcribe.prepare_image_bytes` factors the
existing byte-based preparation; `prepare_card` accepts a concrete optional loader
for the campaign. Default interactive behavior, prompts, image parts, request keys,
full campaign fingerprints and provider/retry implementations remain unchanged.
Journals are indexed per species per invocation; newly discovered manual completions
are matched against actual image content when selected, before a request is sent.

Schema 1-to-2 migration adds `cards.signature` in a transaction and preserves all
results/history/attempts/publications. A failed migration rolls back both column and
version. Read-only status never migrates. Previously completed schema-1 records lack
a metadata baseline and are held stale until a one-time `verify` confirms their saved
content fingerprint; routine continuation cannot silently retranscribe them. Initial
pending cards do not require full-collection hashing before production can begin.

Verification: baseline **203 tests (202 passed, one optional fixture skip)**; final
**215 tests (214 passed, the same skip)**, including both mocked SDK transports.
New cases forbid all image opens/decoding during metadata scans and unchanged
continuation, count a single read per selected image even with retries, compare old
fingerprints/request bytes for both providers and resizing, detect concurrent changes,
exercise explicit full audits with preserved metadata, and verify migration/rollback.
Compilation and `git diff --check` passed. No live model calls were made.

Real metadata discovery took **132.98 seconds**, identifying **10,014 groups / 11,494
JPGs**, with an enforced guard confirming **zero image-content opens**. It found two
filename/grouping issues and 13 unresolved species-folder locations; 201 CSV-only
missing rows are separate. Detailed current findings are in the ignored local
`private/naming-issues-2026-10-18.md` (readable checklist) and
`private/naming-check-fast-2026-10-18.txt` (machine summary). The older October 12 findings below remain
historical. No collection files were changed. The prior scan was stopped and the
20:00 scheduled task was verified disabled before changing runtime files. The user's
pre-existing `.gitignore` edit (`*.lnk`) is preserved separately.

The subsequent normal CLI scan completed discovery in **133.4 seconds**, with
**10,015 groups / 11,495 images**. It accepted the now-corrected Larus argentatus
filename and reported **one remaining filename/grouping issue plus 13 unresolved
species-folder locations**. The short Markdown checklist reflects this newer run.
The CLI exited 20 for those input issues, retained the existing queue, and confirmed
the local quota file was byte-for-byte unchanged. No production run was started.

**18 October 2026 scheduling update:** At the maintainer's request, the default daily
start is now 20:00 Windows local time. The home-desktop task was actually registered
for 20:00 Eastern, under the collection user's interactive account, and verified
**disabled**. It retains the delayed logon recovery trigger. No worker was launched
and no API calls were made. The installer now resolves its repository default after
parameter binding so it works in Windows PowerShell 5.1 as well as PowerShell 7.
Actual registration and trigger/state inspection passed; the Python runtime files
were unchanged. Separate computer counters still require coordination for a combined
self-imposed daily cap; recognized provider daily exhaustion preserves campaign progress.

- `campaign.py`: local SQLite queue/history, physical-card fingerprints, durable
  completion, read-only checkpoint import beyond 48 hours, conservative attempt intents,
  bounded daily continuation, status/JSON/logs, pause/resume, explicit retry/refresh,
  code/host/path binding, publication spool, fallback and offline reconciliation.
- `transcribe.py`: five focused return-value changes add `stop_kind` (`daily`,
  `billing`, `configuration`, `service`). Existing prompts, model settings, cache keys,
  request accounting, retry decisions and interactive behavior are unchanged.
- `test_campaign.py`: generated-fixture acceptance tests using the existing fake
  model client, including actual process termination for worker-lock recovery.
- `scripts/install-campaign-task.ps1`: preview by default; optional installation
  creates a disabled daily/logon task without overwriting existing tasks.
- `docs/campaign.md`, `docs/campaign.example.json`: configuration, deployment, quota
  migration, commands, state semantics, failure recovery and operational limits.
- README, configuration/testing references, project handoff and `.gitignore`: entry
  points, architecture notes and protection for operational state/config/reports.

The new module is explicitly egg-specific orchestration. It imports the current
engine's discovery, prompt preparation, validation, quota, locking and rendering
functions. It does not claim a generic multi-domain backend. No provider or validator
implementation was copied; no extraction that might collide with laptop modularization
was attempted. Campaign accounting wraps `DailyQuota.update`, preserving per-attempt
reservation and Pacific reset logic. The interactive cache still expires at 48 hours.

## Verification

The initial system Python lacked Pillow. A repository-local `.venv` now contains
`docs/requirements.txt`, including both provider SDKs. Baseline: **169 tests,
168 passed, one optional `EGG_SLIP_SAMPLE_DIR` skip**. Both provider transports
used mocks; no real model calls were made. Run the combined suite with:

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_transcribe.py test_campaign.py
```

Final combined result: **203 tests, 202 passed, one optional fixture skip**,
including 34 campaign tests. `git diff --check` and Python compilation also passed.
All 59 local documentation link paths checked across the updated guides resolved.

Campaign coverage includes 25-day continuation, shared/multi-side/uncatalogued records,
deduplication, old/manual journals, missing rows, source/prompt/catalogue changes,
side changes between discovery and requests, compatible approved updates, exact
daily caps, retry accounting, uncertain reservations, fatal/bounded service stops,
pause/resume, wrong-host refusal, disconnected storage, fallback reconciliation,
publication recovery/conflicts, source immutability, read-only status/dry-run, quota
migration/deletion, duplicate workers and stale process locks. The original suite
covers actual Pacific summer/winter reset boundaries and interactive modes.

PowerShell parser validation and the scheduling helper's preview were run without
registering a task. Runtime fingerprints include the four Python runtime files, not
documentation or Git HEAD. A documentation-only commit does not invalidate deployment.
Review/test and `accept-code` are required for runtime updates. Unsupported schema
versions stop rather than resetting state.

## Actual collection findings

The existing Drive `Transcription` and `Family` directories are available. The old
installation contains the catalogue CSV and `transcribe_request_usage.json`; this
clone initially contained neither. The inspected quota history retained three Gemini
model entries. It was read only and not copied/reset. Machine-specific paths remain
in ignored diagnostics/configuration, not reusable source.

The existing engine's filename-only full-CSV dry run found **9,828 groups, 11,277
recognized images, 202 CSV-only missing records, and 48 file/routing issues**, across
1,091 resolved species folders. These describe that selection, not a certified count
of all physical museum objects. They exclude unresolved folders/rejected groups and
do not establish image readability or transcription accuracy. The ignored local
`production-discovery.log` contains detailed findings. No source filenames, scans,
CSV rows, reports or checkpoints were changed.

This is a deployment blocker: campaign discovery intentionally stops on unresolved
input issues. Resolving them requires a separately authorized collection-data task;
do not rename museum scans merely to make automation run. Collection staff should
decide corrections after inspecting each affected species.

## Deployment work remaining

1. Review the implementation and discovery issues. Run the campaign's full decoding/hash
   dry run after resolving routing; it reads every eligible image and may hydrate streamed
   Drive files. Development used generated fixtures for this stronger check rather than
   downloading the entire collection.
2. Choose a stable home-desktop deployment checkout, local state/log/fallback paths,
   correct CSV/Drive paths and `worker_host`. Exclude all database files from sync.
3. Coordinate/stop production writers on both computers. Migrate or reuse **existing**
   quota history exactly once; never continue writing independent old/new counters.
   Configure private credentials through the existing `.env` mechanism.
4. Initialize, scan and inspect status offline. Back up local state/artifacts and quota
   when stopped. Review stale identities before any deliberate refresh.
5. After separate authorization, perform a controlled live deployment check and enable
   the reviewed Windows task. No task installation/enabling was performed here.

The task uses an interactive Windows principal for the user's Drive mount. The user
must remain signed in; after reboot, sign in before the delayed logon trigger can run.
It does not arrange automatic Windows sign-in. Actual enabled scheduling, credential
validity, power recovery, mounted-Drive atomicity and remote sync remain deployment
checks. No remote-upload verification API is included: `drive_local` is filesystem
read-back only and `remote_upload_verified` remains false.

## Integration concerns for the work laptop

- Preserve the five `stop_kind` fields when editing/extracting `Transcriber`; campaign
  continuation distinguishes service/daily pauses from authentication/billing failures.
- Preserve imported engine signatures or adapt orchestration with offline tests during
  modularization. The core engine remains authoritative for transcription behavior.
- Prompt/settings/catalogue/image changes mark results stale rather than silently
  refreshing the campaign. Cross-family/species moves need identity reconciliation.
- Only the designated home computer may run unattended work. Locks are local, and
  interactive runs are not serialized with the whole worker. Coordinate all requests
  against a single production allowance; Drive sync does not make a distributed lock.
- Artifacts are immutable snapshots. Reconciliation appends compatible journals and
  preserves report conflicts. Without hard-link support, an interrupted exclusive-copy
  destination may require its generated partial moved aside before reconciliation.
- Whole-collection discovery stops on any routing/grouping/image-read error. No silent
  exclusion/quarantine workflow was invented. A full Drive outage cannot be solved by
  output fallback when source images are themselves unavailable.
- Continue on the feature branch and inspect upstream before integration. No automatic
  pull/deploy logic runs inside the worker. Do not update runtime code mid-batch.
