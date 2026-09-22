# Repository instructions

## Project mission

This is currently a historical museum egg-slip transcription application. The longer-term goal is a reusable archival-document transcription backend with egg slips as its first domain. Preserve working egg-slip behavior while separating domain assumptions incrementally.

## Architectural direction

Keep reusable provider/execution infrastructure separate from egg-specific discovery, catalogue matching, grouping, prompts, validation, and output. The separation is planned, not implemented. Extract existing responsibilities before inventing interfaces for hypothetical collections. No plugin framework, dynamic loading, or multi-domain UI is needed.

**Extract the egg-specific assumptions now; generalize only as far as the current code naturally supports.** Model comparisons and a behavioral baseline should precede the major extraction.

## Before editing

- Read the relevant code and tests; inspect `git status` and `git diff`. Preserve local/unpushed work.
- Read `PROJECT_HANDOFF.md` for architectural and historical context and the applicable files in `docs/`.
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
- Normal mode reuses only matching completed results. Test mode always makes fresh requests and never touches transcription caches. Test temperature must not affect normal runs.
- Pace and account for every API attempt, including format/service retries. Keep SDK retries disabled and quota state persistent.
- Checkpoint normal results before writing readable output; preserve completed work on interruption or service failure.
- Domain extraction must preserve prompt bytes, image order, validation semantics, output, and compatible cache fingerprints unless an intentional migration is documented.

## Coding and testing expectations

Prefer focused changes, existing dependencies, explicit errors, and small dependency boundaries. Keep configuration centralized. Do not duplicate provider or retry logic, add speculative abstractions, or mix transcription-quality changes into a behavior-preserving extraction.

Run the offline regression suite for changes to parsing, grouping, catalogue matching, output, credentials, retry/quota handling, test mode, or domain/backend boundaries. Install `requirements-openai.txt` for both provider transport tests. See `docs/testing.md` for the optional `EGG_SLIP_SAMPLE_DIR` fixture. Once available, use the curated egg-slip set and reviewed outputs as the modularization baseline; offline replay comparisons should not spend quota. Live before/after comparisons require an authorized test run and allow for model variability.

Update the README/relevant docs when external behavior changes. Update the handoff when responsibilities move. Preserve useful historical notes and clearly label obsolete guidance.

## Code Review Rules

Flag data loss, secret exposure, weakened completion checks, altered transcription semantics, cache collisions/invalidation, or retries bypassing accounting. Also flag egg-specific terminology, paths, schemas, or section rules leaking into reusable modules; duplicated provider/retry implementations; and abstractions without a concrete current need. Do not claim generic multi-domain support before it exists.
