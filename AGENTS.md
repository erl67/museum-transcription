# Repository instructions

## Project mission

This is currently a historical museum egg-slip transcription application. The longer-term goal is a reusable archival-document transcription backend with egg slips as its first domain. Preserve working egg-slip behavior while separating domain assumptions incrementally.

## Current operating and documentation decisions

- Use `gemini-3.5-flash-lite` for production unless the user requests a change. The maintainer is satisfied with its current readings and does not want paid GPT/OpenAI comparison runs. Preserve the existing optional adapter and offline coverage; do not make live comparisons a prerequisite for maintenance or extraction.
- The current default temperature is 1.0 and Flash-Lite thinking level is high. Do not change prompts, generation settings, providers, or cache identity during a documentation-only task.
- Write the README for museum collection staff: lead with the records, preservation of source evidence, review, and practical workflow. Avoid overt AI/large-language-model framing or promotional accuracy claims. Document the Gemini service, transmitted images/hints, credentials, and request costs accurately where operationally relevant; retain exact technical names in reference docs.
- Distinguish a structural `OK` from human verification, and CSV-only `(MISSING)` blocks from transcriptions. Maintainer satisfaction is not a measured accuracy percentage or a cross-model ranking.

## Architectural direction

Keep reusable provider/execution infrastructure separate from egg-specific discovery, catalogue matching, grouping, prompts, validation, and output. The prompt policy is already in `egg_slip_prompt.py`, and provider usage/cost accounting is in `token_usage.py`; broader separation remains planned. Extract existing responsibilities before inventing interfaces for hypothetical collections. No plugin framework, dynamic loading, or multi-domain UI is needed.

**Extract the egg-specific assumptions; generalize only as far as the current code naturally supports.** Establish a behavioral baseline from the chosen Gemini workflow and reviewed saved responses before major extraction. Further paid model comparisons are not required.

## Before editing

- Read the relevant code and tests; inspect `git status` and `git diff`. Preserve local/unpushed work.
- Read `docs/PROJECT_HANDOFF.md` for architectural and historical context and the applicable files in `docs/`. Current operating decisions supersede older comparison plans in historical notes.
- Run `python -m unittest -v test_transcribe.py` before substantial changes when practical. Report skipped tests as well as failures.
- Current code/tests define implementation. The handoff explains rationale; proposed architecture does not override working behavior.

## Data safety

- Do not modify, delete, rename, or bulk reorganize source museum scans or the source CSV unless explicitly requested.
- Never commit keys, `.env`, local quota state, generated caches/reports, or unreviewed collection data. Use `.env.example` only for empty placeholders.
- Do not use live API requests as routine verification. Use offline tests; request execution must be part of the user's authorized task.
- Preserve uncertainty and visible historical wording. Never replace an uncertain reading with invented certainty.

## Behavioral invariants

- Keep all sides of one physical card together and ordered; a lone front/A is valid. Do not relabel a lone back as a front.
- Match complete E-numbers, including any number on a shared slip; preserve leading zeros and side ambiguity checks. `E123*` is console mode, not wildcard matching.
- Retain explicitly uncatalogued material in the existing selection scopes and at the end of reports.
- Do not discard substantive unexpected back text or failed response text to make validation pass.
- Preserve the egg-slip SOP, CM/filename banners, two blank lines, and status meanings unless a requested change requires otherwise.
- Normal mode reuses only matching completed results no more than 48 hours old; older journal history remains intact. Test mode and `*`, `!`, `@` fresh modes never touch transcription caches. Test temperature must not affect normal runs; `@` deliberately selects its complete alternate profile.
- Missing-card CSV blocks stay within the selected scope, preserve duplicate rows and partial dates, refresh without requests or journal entries, and sort before uncatalogued scans. Rejected scans and missing/ambiguous directories must not be disguised as absent catalogue images.
- Pace and account for every API attempt, including format/service retries. Keep SDK retries disabled and quota state persistent.
- Checkpoint normal results before writing readable output; preserve completed work on interruption or service failure.
- Domain extraction must preserve prompt bytes, image order, validation semantics, output, and compatible cache fingerprints unless an intentional migration is documented.

## Coding and testing expectations

Prefer focused changes, existing dependencies, explicit errors, and small dependency boundaries. Keep configuration centralized. Do not duplicate provider or retry logic, add speculative abstractions, or mix transcription-quality changes into a behavior-preserving extraction.

Run the offline regression suite for changes to parsing, grouping, catalogue matching, output, credentials, retry/quota handling, test mode, or domain/backend boundaries. Install `docs/requirements.txt` for both provider transport tests; this does not require credentials or paid requests. See `docs/testing.md` for the optional `EGG_SLIP_SAMPLE_DIR` fixture. Use the curated egg-slip set and deliberately reviewed outputs as the modularization baseline; a file labelled manual transcription is not automatically a complete verified reference. Offline replay comparisons must not spend quota. Live before/after checks require an authorized run and allow for model variability.

Update the README/relevant docs when external behavior changes. Update the handoff when responsibilities move. Preserve useful historical notes and clearly label obsolete guidance.

Verify setup paths, local documentation links, actual sample counts, and Git tracking before describing them. The dependency manifest currently lives in `docs/requirements.txt`; root requirements files and `.env.example` are absent. Some reference reports are already tracked despite the output-directory ignore rule. Preserve them and do not add generated reports or collection data merely to reconcile documentation.

## Code Review Rules

Flag data loss, secret exposure, weakened completion checks, altered transcription semantics, cache collisions/invalidation, or retries bypassing accounting. Also flag egg-specific terminology, paths, schemas, or section rules leaking into reusable modules; duplicated provider/retry implementations; and abstractions without a concrete current need. Do not claim generic multi-domain support before it exists.
