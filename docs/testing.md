# Testing and the behavioral baseline

There are two different activities: deterministic offline regression tests and live, quota-consuming model comparisons. Neither should be mistaken for a measured accuracy benchmark without human-reviewed source readings.

## Offline regression suite

From the repository root:

```text
python -m pip install -r requirements-openai.txt
python -m unittest -v test_transcribe.py
```

`requirements-openai.txt` includes the Gemini/image/timezone dependencies as well as OpenAI, enabling both real-SDK transport tests. `unittest` is in the standard library. The suite uses temporary CSVs/JPEGs, fake clients/clocks, and SDK HTTP mock transports with dummy credentials. It makes no live provider calls and does not need the production CSV, Drive mount, or `.env`.

Check the final skipped count, not only `OK`. Missing SDKs cause client/transport tests to skip. Pillow is required even for the synthetic JPEG tests. Python 3.10+ is the source/dependency floor; the handoff was run on Python 3.12.14/Linux, not every supported Python/OS combination.

The suite currently covers:

- Credential lookup from unrelated launch directories, `.env` precedence/encodings, hidden `.txt` extensions, and provider-specific keys/endpoints.
- Profile selection, explicit overrides, invalid settings, timezone reset boundaries, persistent attempt counts, corrupted/unwritable quota state, and daily/billing stops.
- Species/row routing, duplicate CSV records, ambiguous directories, shared numbers, leading zeros, A/B/numeric order, missing fronts, duplicate sides, `_exchanged`, and uncatalogued handling.
- Original image bytes, EXIF correction, optional resize, payload budget, and cache identity/invalidation.
- Completion/refusal/token-cutoff handling, answer-vs-thought extraction, flexible back headings, multiple annotation sections, empty-note markers, LaTeX, and bounded correction retries.
- Cache reuse, forced refresh, damaged journal recovery, checkpoint-before-report ordering, and local locks.
- Mixed-species tests, both temperatures/model tags, repeat fresh calls despite cached production results, independent reports, custom paths, and test quota stops.
- Actual Gemini/OpenAI SDK serialization and retry disabling through simulated HTTP transports.

## Missing-card CSV regression checks

Build **2026-10-07.1** passes **169 offline tests: 168 passed, one optional `EGG_SLIP_SAMPLE_DIR` skip**, including both mocked SDK transports. Ten new tests cover the script-relative default CSV, selected fields and blank B/Case header, blank omission and zero/multiline preservation, full/partial/conflicting dates, zero-request CSV-only output without keys/quota/journals, numerical ordering before uncatalogued scans, shared/back/rejected scan presence, selection scope, read-only console/dry-run behavior, duplicate rows, updated CSV values, subsequent image arrival, and test-mode isolation.

The pre-edit suite had one date-dependent failure in the individual-report test: setup used the current quota date while later runs mocked October 5. Setup now uses the same fixed quota date. Windows sandbox temporary-fixture permissions required running the suite outside the sandbox. Production read-only checks loaded the relocated CSV and identified E385 as absent from the Hirundo rustica JPEG folder; the CSV renderer produced its selected fields and `May 30, 1891` date without requests or source changes.

## Single-card fresh checks

Enter `E9323!` at the interactive target prompt, or run `python transcribe.py "E9323!"`. It routes through the production CSV and family/species JPEG folder, submits all sides of the selected physical card, prints the full result, and saves `E9323_g35fl_Hylopezus_perspicillatus_YYYYMMDD_HHMM.txt` with Gemini 3.5 Flash Lite. Enter `E9323@` to force the complete Gemini 3.8 Flash profile and save `E9323_g38f_Hylopezus_perspicillatus_YYYYMMDD_HHMM.txt` in the same family directory. It never reads or writes transcription caches. Use `--dry-run` to preview without requests or files. `!` uses the selected normal profile settings; `@` uses the 3.8 Flash profile (5 RPM and 20 daily attempts, shared with other 3.8 runs and including retries). Compatible explicit CLI overrides apply; `TEST_TEMPERATURE` remains specific to the mixed-species `tests` target. Daily accounting, pacing and bounded retries apply to every attempt.

Build **2026-10-05.2** passed **159 offline tests: 158 passed, one optional `EGG_SLIP_SAMPLE_DIR` skip**, including both mocked SDK transports. Added checks verify interactive/direct `@` profile selection before engine initialization, request/report model identity, model-tagged filename collisions, fresh requests despite caches, persistent 20-attempt quota enforcement on retry/restart, dry-run isolation and explicit-option validation. The baseline was 155 tests (154 passed, the same skip). A production `E9323@ --dry-run` matched the expected one-image card without requests or output files. No live API requests or source-data changes were made.

Historical build **2026-10-05.1** passed **155 offline tests: 154 passed, one optional `EGG_SLIP_SAMPLE_DIR` skip**, including both mocked SDK transports. New coverage checks the interactive suffix, fresh repeated requests despite production cache entries, unchanged journals/source files, timestamp collision counters, terminal/saved output, ordered sides, shared-number/leading-zero selection, failed response retention, dry-run isolation, invalid suffixes and opening the report before spending quota. The pre-edit baseline passed 149 of 150 tests with the same optional skip. Sandbox temporary-directory permissions initially prevented fixture writes; the suite ran successfully outside the sandbox. No live API requests were made.

## Optional original-image fixture

`DatasetTest.test_supplied_scans_preserve_pixels_and_pair_correctly` uses `EGG_SLIP_SAMPLE_DIR`. Without it, that test skips. The directory must contain **exactly three lowercase `.jpg` files matching `*Accipiter_gentilis*.jpg`**: E4927 plus E4268 front/back. Recognized original attachment names were:

```text
02-Accipiter_gentilis_E4927.jpg
03-Accipiter_gentilis_E4268-A-.jpg
04-Accipiter_gentilis_E4268-B-.jpg
```

The test also accepts their unprefixed conventional names; it copies/normalizes names inside a temporary test directory without modifying the originals. The test only checks image handling and grouping, not handwriting accuracy. These three originals were available in Work for verification but are not included in the repository handoff. The current 10-card / 18-image curated set is separate from this older optional fixture. Do not point this variable at a folder with additional matching Accipiter images; the current exact-three assertion would fail.

PowerShell, with a real local directory substituted:

```powershell
$env:EGG_SLIP_SAMPLE_DIR = "PATH\TO\original-three-image-fixture"
python -m unittest -v test_transcribe.py
```

For a portable default run without those originals, leave the variable unset and report the one expected skip. Missing sample images do not prevent repository setup or ordinary offline tests. On Windows, the specific POSIX second-lock test also skips; the Windows lock implementation must be exercised on that deployment.

## Live representative-card comparisons

The current curated `tests/inputs/` set contains 10 physical cards / 18 JPEGs across several species. Choose real examples that exercise the existing workflow: easy fronts, faint/dense handwriting, A/B narrative backs, collection headings, corrections/stamps, grouped dimensions/ditto marks, signatures, shared E-numbers, and uncatalogued records where available. This is selection guidance, not an assertion those examples have already been committed.

Keep JPG/JPEG files directly in the input directory with original names. One request contains all sides of one physical record, before any retries. There is no enforced 15-card limit. The master CSV remains required, even for `tests`, but normal family/species folders are unnecessary. Unmatched numbers get a review flag; uncatalogued images get no unrelated hints.

Test paths default to `tests/inputs/` and `tests/outputs/` beside the script, independent of the Family folder and launch directory. From the repository root:

```text
python transcribe.py tests --dry-run
python transcribe.py tests --model gemini-3.5-flash-lite
python transcribe.py tests --model gemini-3.8-flash
```

The configured CSV path is used; `--csv` overrides it. Only the first command is offline. Review its card count/order before launching paid/quota-consuming runs. Substitute another configured model for the next comparison. Alternatively change `MODEL` and `TEST_TEMPERATURE` near the top of the script and type `tests` at its prompt (`test` is also accepted). Each launch runs one combination.

For the four configured OpenAI models, install its optional dependency, supply `OPENAI_API_KEY`, and use `--model gpt-5.6-luna --temperature auto` when testing without a temperature override. Normal and test numeric defaults are now 1.0; `TEST_TEMPERATURE` remains an independent test-only setting. Astra always omits temperature and rejects explicit numeric overrides. See [configuration](configuration.md) for the model IDs and parameter limitations. Account availability and actual parameter acceptance have not been established by mocked tests; do not assume any configured profile is guaranteed accessible.

A non-dry test creates the input/output directories if absent. An empty folder causes no API calls or report and returns code 1 with instructions. A dry run creates nothing, does not decode the images or test credentials, and returns code 1 if its folder is absent. Test input and output cannot be the same resolved directory. `test --console-only` is invalid.

## Isolation, naming, and quota

Each test starts over, never reads/writes a `Journal`, and sends its own images/prompt/relevant CSV hints. It does not use an earlier generated answer as input. This guarantees fresh application requests, not control over any provider-internal caching or determinism. `--force` is unnecessary.

Example report names (illustrations, not committed outputs):

```text
test_20260922_1425_g3.5-f-l_t0.1.txt
test_20260922_1425_2_g3.5-f-l_t0.1.txt
test_20260922_1430_g3.8f_t1.0.txt
test_20260922_1435_gpt-5.6-luna_tauto.txt
```

The report includes full model/provider, effective temperature, input path, and card count. It does not yet contain a complete reproducibility manifest, image hashes, per-card token costs, or every generation setting. Keep a separate comparison record of script version/commit, input hashes, CSV/hint policy, resizing, thinking/reasoning/image-detail settings, and run time. Do not put sensitive catalogue content into a public baseline without review.

Daily accounting is shared with normal calls and retries. Twenty daily requests permit two temperatures on ten cards only if no retry is needed; fifteen cards at two temperatures require at least thirty requests. A stopped test retains completed output, but its next invocation starts from card one. There is no subset selector or resume within `test`; adjust the chosen input set before an authorized run when necessary, preserving the original museum scans.

## Establishing a baseline before modularization

1. Freeze the selected image set and relevant catalogue hints/settings for a comparison round. Record exact file hashes so later corrections are not mistaken for model changes.
2. Use the chosen temperature of 1.0 for models whose profiles accept it; compare prompt/model changes without introducing an unnecessary temperature sweep. Evaluate missing lines, wrong readings/numbers, unsupported inference, side omissions, formatting, latency, and attempts. Avoid judging by tidy formatting alone.
3. Human-review especially difficult readings. Distinguish acceptable uncertainty from an invented confident answer and from a harmless formatting variation.
4. Retain a small reviewed reference set and representative provider responses locally or in explicitly publication-approved fixtures. The [Fringilla review checklist](fringilla_review.md) records concrete checks and unresolved readings from the September 23 comparison; it is a partial visual-review reference, not a human-certified full gold transcription or an automatic accuracy scorer.
5. Before moving domain code, capture deterministic expectations for grouping, prompt strings, ordered image bytes/labels, cache keys, validation, and rendered output. Existing mocks are useful; reviewed sample responses would strengthen them.
6. During extraction, replay the same provider responses offline and compare those artifacts exactly where behavior is intended to be identical. Do not depend solely on new live calls: nondeterministic output could hide a code regression or falsely suggest one.
7. After structural equivalence, use the same curated samples for authorized live spot comparisons if needed. Keep prompt tuning separate from architectural changes.

Raw reports remain ignored in `tests/outputs/` (and in the previous `outputs/` location). A future reviewed baseline should be deliberately selected and documented, not created by committing every run. Ordinary text differences are not a reliable accuracy metric without aligned, human-reviewed references.

## Regression focus after changes

| Changed area | Required attention |
| --- | --- |
| Filename/CSV parsing or discovery | Exact-number matching, shared slips, zeros, case, suffixes, ambiguity, duplicate routing, unmatched/uncatalogued scopes. |
| Grouping or image loading | Physical-card boundaries, all sides and order, front-only/back-only/gaps, bytes/EXIF/resize, no source mutations. |
| Prompts or validation | Historical wording policy, section rules, substantive unexpected text, notes/brackets, LaTeX, bounded correction, intentional cache invalidation. |
| Output/journal handling | Banners/order/spacing/status, collision safety, fsync ordering, interrupted writes, reuse/failure semantics. |
| Provider/API/retry/quota | Both transport tests, no hidden SDK retries, per-attempt reservations, pacing, reset/error classification, timeout and stop behavior. |
| Test mode or future domain boundary | Fresh calls, no journal access, production-temperature/cache stability, mixed metadata, file paths, original prompt/output/cache equivalence. |

## Brandt reading checklist - build 2026-09-30.3

Both baseline and final offline suites ran **150 tests: 149 passed, one expected skip** (optional `EGG_SLIP_SAMPLE_DIR` fixture not configured), including both mocked provider transports. Existing collector-selection, disabled-hint, shared-record scoping and prompt/cache tests cover the expanded exact Brandt entry. A read-only before/after assembly check against the actual CSV confirmed changed prompt hashes and exactly one guidance block for E4443-E4447, E7466 and E6785. Base-prompt bytes and control prompts for another collector, Steinbach, a blank collector and disabled hints were unchanged.

The source images and supplied reports were reviewed for recurring failures; the checklist does not embed corrected specimen text. There was no fresh live transcription run, so these checks do not measure handwriting accuracy or demonstrate that the model obeys the new reread instructions. Existing scans, CSV, reports, journals and quota state were not edited.

## Partial-date prompt - build 2026-09-30.2

The baseline and final offline suites each ran **150 tests: 149 passed, one expected skip** (optional `EGG_SLIP_SAMPLE_DIR` fixture not configured). Inspection of Gavia E4431-E4434 confirmed that the day position is visibly empty in each image, while the source CSV's collected-date field is blank. `build_prompt` includes no CSV date columns, so no day was provided as a hint. The current prompt explicitly distinguishes a blank day slot from a visible day and from punctuation or set-mark digits. These are prompt and source inspections, not a live model accuracy test; no API request, source scan, CSV, historical report or journal was changed.

## Conditional collector detail - build 2026-09-30.1

Both baseline and final `python -m unittest -v test_transcribe.py` runs completed **150 tests: 149 passed, one expected skip** (optional `EGG_SLIP_SAMPLE_DIR` fixture not configured). Both provider SDK transports ran against mocks. Updated coverage checks that full Steinbach guidance appears exactly once for matching hints and is absent for Brandt, blank collectors and disabled hints; the compact visible-name fallback remains. Shared-slip selection, collector-rule cache fingerprints and initial/retry side requirements remain covered. Retry requirements contain no Steinbach-specific text.

The base prompt shrank by 133 words / 855 characters compared with build 2026-09-29.4, with additional savings in shared output requirements. No live API calls were made, so reading quality and billed token savings were not measured. This prompt change intentionally produces fresh fingerprints for future selected runs.

## Steinbach German translation rule - build 2026-09-29.4

The pre-edit offline baseline completed **148 tests: 147 passed, one expected skip** (optional `EGG_SLIP_SAMPLE_DIR` fixture not configured). Read-only inspection of the production CSV found 564 records whose Collector value contains `Steinbach`; the current spelling is consistently `Steinbach, José`, and all five supplied catalogue numbers resolve to it.

The final `python -m unittest -v test_transcribe.py` run completed **150 tests: 149 passed, one expected skip**, including both mocked provider SDK transports. New cases cover case/whitespace-insensitive surname containment, unmatched names, shared-slip catalogue scoping and deduplication, the visible-name fallback with CSV hints disabled, required German/parenthetical/disclosure instructions, and prompt/cache identity when containment guidance changes. Offline tests establish prompt assembly and execution behavior, not translation or handwriting accuracy.

No live API requests were made. The source scans, production CSV, existing reports, journals, and quota state were not modified. Existing cache entries and reports remain available; changed prompt bytes intentionally produce fresh fingerprints for future selected requests.

## Active catalogue numbers and E8157 reading - build 2026-09-29.3

The pre-edit offline baseline completed **148 tests: 147 passed, one expected skip** (optional `EGG_SLIP_SAMPLE_DIR` fixture not configured). This update changes prompt wording and version labels only. Read-only inspection of the supplied E9551 and E8157 images identified active catalogue numbers and supported “long” in the latter nest sentence. The post-edit suite also completed **148 tests: 147 passed, one expected skip**, including both mocked provider SDK transports. Offline tests confirm software behavior, not the next model reading. No live API requests or saved report edits were made.

## Further specimen-reading refinements - build 2026-09-29.2

Both the pre-edit baseline and final `python -m unittest -v test_transcribe.py` run completed **148 tests: 147 passed, one expected skip** (optional `EGG_SLIP_SAMPLE_DIR` fixture not configured). This update changes prompt wording and version labels only, retaining the earlier validator changes. Existing policy, fingerprint, request metadata and token-rendering tests pass. No model responses were generated; improvements in reading accuracy remain to be assessed on subsequent authorized runs.

Read-only inspection confirms the pasted CM1537 example matches the September 23 report, whereas the September 29 report includes token counts and the complete common name. The current renderer includes a token line even for legacy results lacking usage, displaying `unknown` instead of inventing counts. Reports were not rewritten.

## Concise annotations and review policy - build 2026-09-29.1

Baseline: **145 tests, 144 passed, 1 expected skip**. After this update, `python -m unittest -v test_transcribe.py`: **148 tests, 147 passed, 1 expected skip** (optional `EGG_SLIP_SAMPLE_DIR` fixture not configured). Both installed provider SDK transports ran against offline mocks.

The revised cases accept missing colons, shared field lines, multiline measurements and narrative backs without layout warnings. New cases preserve recognized form codes without review or retry, retain genuine uncertain text and other brackets alongside them, and update derived cached warnings without changing source text, provenance or journal bytes. Existing completeness, side-order, failed-text retention, quota/retry, prompt-fingerprint, cache-age and lock tests pass.

No live requests were made. Scans, CSV, existing reports and production journals were not edited. The revised prompt intentionally changes cache fingerprints for future requests; the 48-hour age limit is unchanged. Offline tests establish software behavior, not an improvement in model reading accuracy. The older field-format heuristics documented below are superseded by this revision.

## Fringilla refinement verification - build 2026-09-23.4

Baseline: **133 tests, 131 passed, 2 expected skips**. After this update: **142 tests, 140 passed, 2 expected skips** (POSIX locking on Windows and the absent optional original three-image fixture). Both SDK transports ran against offline mocks.

Nine new tests cover numeric defaults and overrides; format hints on front/back fields without altering narratives, notes or multiline measurements; no extra requests for those warnings; truthful bracket-count labels; derived legacy-cache review; request metadata checkpointing and retention across reuse; failed test output without journals; and provider-specific metadata/omitted settings. The existing prompt-policy test also covers the revised fidelity rules. A read-only replay flags formatting problems in all seven records in each supplied Fringilla report. This is format detection, not a semantic-accuracy measurement.

No live requests were made. Source scans, CSV, existing reports and production journals were not edited. The new prompt and changed numeric defaults intentionally create new input fingerprints on future runs; the fingerprint algorithm itself is unchanged. The [review checklist](fringilla_review.md) keeps uncertain readings separate from the concrete comparison checks.

## Species routing verification - build 2026-09-23.2

The trailing-period routing fix completed **125 tests: 123 passed, 2 skipped** (POSIX locking on Windows and the absent optional three-image fixture). Three new tests cover dotted CSV names and targets, unchanged source metadata, direct and genus-nested directories, and retained rejection of unsafe paths. The baseline was 122 tests with the same two skips.

The real `E2573 --dry-run` resolves `Serinus_sp_E2573.jpg` successfully. Range `3207-3308 --dry-run` passes the former `Serinus_sp.` failure and discovers 100 card groups, but separately reports no matching JPEG folder for `Spinus_spinus`. No live API requests or source-data changes were made.

## Prompt revision verification - build 2026-09-23.1

The September 23 run completed **122 tests: 120 passed, 2 skipped** (the Windows/POSIX lock test and absent optional three-image fixture). Both SDK transports ran offline. Seven new tests cover exact CSV collector selection and normalization, disabling hints/guidance, shared and conflicting records, unmatched/uncatalogued fallbacks, prompt-driven cache identity with unchanged image parts, reviewed policy requirements, and common initial/retry side instructions.

The baseline had one existing failure in the repeated-test/cache fixture. It now sets temperature explicitly and freezes time across both normal and sample runs, so the expected filenames and six-attempt counter are independent of user configuration and the real date. Production temperature and quota logic were not changed.

This prompt revision intentionally changes assembled prompt bytes and corresponding cache keys. The regression suite checks integration and preserved execution behavior; it does not establish improved handwriting accuracy. The supplied comparison reports informed the instructions, but no new live responses or human-certified golden transcriptions were generated. The earlier verification records below are historical.

## Current checkout verification — build 2026-09-22.1

The initial Windows checkout contained build 2026-09-21.1 and 103 tests; its documentation described later Work code that was absent. The baseline passed with two skips. After implementing the mixed-species test route and OpenAI profiles, 115 tests ran: 113 passed and two skipped (POSIX locking on Windows and the older optional three-image fixture). Both installed SDKs were tested through mocked HTTP, including each configured OpenAI model. The actual sample directory dry run found 10 cards / 18 images without changing scans or spending quota.

The Windows sandbox denied temporary fixture access; the offline suite was run with permission outside that sandbox. This is a test-environment permission issue, not evidence of an application regression.

## Historical Work handoff verification — 22 September 2026

The following is the earlier Work environment record, not the initial state observed in this Windows checkout.

The authoritative Work implementation was overlaid onto a checkout of the older public repository. Before documentation changes, **115 tests passed with zero skips**. The post-documentation verification repeats the same suite; its final result is recorded in [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md#current-state-and-verification).

Environment: Python 3.12.14/Linux; google-genai 2.23.0, Pillow 12.3.0, tzdata 2026.3, openai 3.16.2; HTTPX 0.28.1 available to transport tests. Both SDKs and the three original Accipiter images were available. Dependency pins derive from that inspected environment. The whole master CSV, Windows/Drive deployment, current key validity, live model output, actual limits, and comparative transcription accuracy were not exercised. No live API calls were made.

Production and test Python files are unchanged by this documentation task. An offline pass validates software behavior under its fixtures, not a claim of 99% reading accuracy or proof a newer model is better.


## Cache age and lock cleanup - 23 September 2026

Build 2026-09-23.5 adds deterministic boundary checks at 47, 48, and 49 hours; checks undated, malformed, naive and future timestamps; verifies a stale result makes a fresh offline request while preserving the previous journal entry; and exercises Windows mutex contention and cleanup of legacy lock files. The former Windows lock skip now runs with a second thread. `python -m unittest -v test_transcribe.py`: **145 tests, 144 passed, 1 expected skip** (optional `EGG_SLIP_SAMPLE_DIR` fixture absent). No live requests were made.

## Usage/header regression update - 23 September 2026

Build 2026-09-23.3: `python -m unittest -v test_transcribe.py` ran **133 tests: 131 passed, 2 expected skips** (POSIX lock test on Windows; optional `EGG_SLIP_SAMPLE_DIR` fixture absent). Both installed SDK transports run against offline mocks. New coverage verifies Gemini/OpenAI token normalization, reasoning and cached-input costs, format/service retry accounting, incomplete-response usage retention, compact headers, legacy caches, zero spending on reuse, file-scoped footers, missing usage, dated pricing and long-context rates. Existing interruption coverage now verifies the partial usage footer. No live requests were made.
