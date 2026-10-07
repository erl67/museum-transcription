# Project handoff: museum transcription

Originally prepared 22 September 2026 for moving development from ChatGPT Work to Codex. Updated through **7 October 2026**, application build **2026-10-07.1**. The current overview and execution map below describe this checkout; dated entries preserve the history of earlier builds. This is technical institutional memory, not a specification for a framework that already exists.

## Production choice and documentation update - 7 October 2026

The maintainer intends to process the collection with **`gemini-3.5-flash-lite`** and is satisfied with its current readings. Retain the existing temperature 1.0 and high-thinking defaults. Paid GPT/OpenAI comparisons are not planned and are not a prerequisite for maintenance or modularization. Keep the optional adapter and offline transport coverage intact. The earlier roadmap calling for OpenAI comparisons is superseded by this decision.

The README now leads with museum records, source fidelity, collection review, and practical operation. It avoids overt AI/large-language-model framing while accurately describing the configured Gemini service, transmitted images and hints, request accounting, and the limits of structural validation. Maintainer satisfaction must not become an invented benchmark or accuracy percentage.

This pass changes documentation only. It corrects setup paths, sample inventory, tracked-report descriptions, stale implementation claims, relative links, and the development sequence. Existing code, prompts, default settings, source data, saved reports, journals, and quota state are unchanged. The existing README's Apache License 2.0 declaration is retained; no standalone `LICENSE` file is present, and software licensing does not establish rights over collection materials.

## Current state and verification

The application currently provides:

- Species, exact E-number, and CSV-row selection; both supported family/species folder layouts; complete-number matching and ordered physical-card groups, including shared and uncatalogued slips.
- Normal per-species reports with 48-hour matching-result reuse, fresh `*` console checks, fresh `!` individual reports, and the complete alternate Gemini profile selected by `@`.
- CSV-only `(MISSING)` blocks for selected catalogue records without JPEGs, preserving selected fields, duplicate rows, and partial dates without spending quota.
- Separate egg-slip reading instructions, scoped Brandt and Steinbach guidance, partial-date and alteration rules, flexible side-section validation, and preserved uncertainty/failed response text.
- Per-attempt pacing, persistent daily accounting, bounded service/format retries, request provenance, token/cost estimates, durable checkpoints, collision-safe reports, and local locking.
- Fresh mixed-species sample runs independent of transcription journals, plus offline regression tests using generated fixtures and simulated service transports.

The actual curated folder now contains **11 cards / 19 JPEGs**, verified by read-only discovery with no grouping issues. Several reference reports and two files named manual transcriptions are already tracked in `tests/outputs/`; these need deliberate review before becoming a complete regression reference. The synthetic ten-card/eighteen-image test remains valid as its own fixture.

The dependency manifest is `docs/requirements.txt`. Root `requirements.txt`, `requirements-openai.txt`, and `.env.example` are absent; follow the README for Gemini-only setup and create a local `.env` directly. Earlier handoff claims about those root files describe the old snapshot, not this checkout.

Verification for this documentation update: **169 offline tests, 168 passed and one optional `EGG_SLIP_SAMPLE_DIR` skip**, on Windows/Python 3.14, including both SDK transport tests with mocked HTTP. Sandbox fixture permissions required execution outside the sandbox. No live service calls were made. The current task began with a clean Git working tree. All 69 local documentation links and heading targets were checked.

## Repository CSV and missing-card output - 7 October 2026

Build **2026-10-07.1** finds `EggSlipReorganizationProject_FULL.xlsx - Full List.csv` beside `transcribe.py`; `--csv` still overrides it. The Family default remains unchanged. Blank column B is labelled `Case` in memory only. Production species, row-range and exact-number selections now insert CSV-only `CM... (MISSING)` blocks for absent JPEGs. The maintainer confirmed the final column cutoff is BD/Remarks, omitting BG/basisOfRecord. Date columns AG-AJ become one readable date while preserving partial dates and unusual/conflicting values. See [output rules](transcription_rules.md#missing-card-csv-blocks).

The new egg-specific `missing_catalogue_numbers`, `missing_collection_date`, and `missing_output_block` helpers remain in `transcribe.py`; no reusable infrastructure or provider responsibilities moved. CSV blocks bypass prompts, images, APIs and transcription journals, refresh each run, keep duplicate rows, and sort with numbered cards before uncatalogued scans. An all-missing selection can save a report without a key, quota state or journal. Successful CSV fallback is counted separately rather than failing the run. Rejected filenames/side groups do not become missing-card data; existing directory ambiguity/access checks still apply. Mixed-species tests remain scan-only. Prompt bytes, cache fingerprints, scan transcription rendering, and retry/accounting paths are unchanged.

Verification: **169 offline tests, 168 passed and one optional original-scan fixture skip**, including both mocked SDK transports. Baseline: 159 tests with one existing date-dependent individual-report quota assertion failure and the same skip; its setup now uses the same fixed date as subsequent mocked runs. Sandbox temporary-fixture and Drive reparse-point writes required elevated execution. Read-only production checks verified the new CSV path and E385's absence/CSV rendering. Source scans/CSV and old reports were not edited; no live API requests were made. Earlier notes describing machine-specific CSV defaults or missing-number failures are superseded by this entry.

## Flash-Lite high-thinking default - 5 October 2026

Build **2026-10-05.3** sets only the Gemini 3.5 Flash-Lite profile to `thinking_level="high"`, as requested after review of E5344. Normal, test, and single-card runs inherit it; explicit CLI overrides including `auto` remain available. Other model defaults, temperature, and request caps are unchanged. Prompt bytes remain unchanged; generation settings intentionally change the input fingerprint, preventing reuse of old default-setting results without deleting saved history. No responsibilities moved.

Baseline and final offline suites: **159 tests, 158 passed, one optional scan-fixture skip**, including both mocked provider transports. Sandbox temporary-fixture permission failures required running the suite outside the sandbox. Explicit `auto`/`medium` overrides and the unchanged 3.8 shortcut default were checked locally. No live requests were made.

## Strong-model single-card shortcut - 5 October 2026

Build **2026-10-05.2** adds `E9323@` to force the configured Gemini 3.8 Flash profile for a fresh terminal reading and individual family-folder report. Single-card filenames now include the actual model: `E9323_g38f_Hylopezus_perspicillatus_20261005_1045.txt` for `@`, and `E9323_g35fl_Hylopezus_perspicillatus_20261005_1045.txt` for `!` with 3.5 Flash Lite. Old untagged reports remain intact; combined-test names are unchanged. Both suffixes keep all sides together and bypass transcription journals.

Profile application/validation moved from `parse_args` into the shared `configure_model_profile` helper so interactive selection can resolve the complete profile before limiter, quota and client initialization. Original explicit CLI overrides are retained and revalidated against the selected profile. `@` uses the existing persistent 3.8 counter and its default 20-attempt daily cap, including retries. Normal model selection, prompts, cache fingerprints, source data and provider/retry implementations are unchanged.

Baseline: 155 offline tests (154 passed, one optional scan-fixture skip). Final: **159 tests (158 passed, the same skip)**, with both mocked provider transports. A production `E9323@ --dry-run` confirmed the one-image card and 3.8 profile without API calls or output writes. No live requests were made. The untagged filename examples in the earlier build note below are historical and superseded for new single-card reports.

## Individual fresh card reports - 5 October 2026

Build **2026-10-05.1** adds the exact E-number `!` suffix, such as `E9323!`, for a fresh terminal reading plus a timestamped individual report in the CSV-routed family directory: `E9323_Hylopezus_perspicillatus_20261005_1045.txt`. It uses the existing discovery, prompt, image, provider, validation, quota and report-writing paths, without opening a transcription journal. Normal settings apply; `TEST_TEMPERATURE` still applies only to the mixed-species test target. Existing `*` console-only behavior and normal cache reuse remain intact. All sides/shared numbers stay together; same-minute report collisions get counters and failed answer text remains visible and saved.

No responsibilities moved, prompt bytes or cache fingerprints changed, or source collection data was edited. The baseline ran 150 offline tests (149 passed, one optional scan-fixture skip); the final suite ran **155 tests (154 passed, the same skip)** with both provider transports mocked. Initial sandbox fixture-write errors were resolved by running the offline suite outside the sandbox. No live requests were made. See [testing](testing.md#single-card-fresh-checks).

## Brandt reading checklist - 30 September 2026

Build and prompt **2026-09-30.3** expand the existing exact-name `COLLECTOR_PROMPTS["Brandt, Herbert W."]` entry. Comparison of the supplied Gavia E4443-E4447 reports (2026-09-29.3 and 2026-09-30.2) with their scans exposed misplaced continuations, invented identification text, stamp/field confusion, altered signatures and small numeric-mark errors. Cinclus E7466 and Columbina E6785 provide further dense-prose and marginal-writing examples. The new checklist requests a silent second visual reading, letter/word comparison within the same supplied hand, faithful unusual prose, complete continuations and a separate numeric audit. The original conditional signature guidance is retained.

Read-only CSV inspection found 3,332 exact Brandt rows (about 32.7% of 10,190 rows); all seven supplied records match. Six joint Maguire/Brandt rows use a different existing collector string and are not silently aliased. No matching algorithm, base prompt, provider setting, validator or execution behavior changed. The seven sample prompts each contain the new guidance once. Control prompts for another collector, Steinbach, blank collectors and disabled hints are byte-identical to their pre-edit values. Only affected assembled prompts receive new cache fingerprints; saved history remains intact.

Offline baseline and final suites each ran **150 tests: 149 passed, one optional fixture skip**, with both provider transports mocked. No live requests or source-data changes were made. This verifies integration and scope, not a measured improvement in model reading accuracy. See [transcription rules](transcription_rules.md#brandt-handwriting-and-dense-narratives).

## Partial dates on typed Carnegie forms - 30 September 2026

Build and prompt **2026-09-30.2** add a shared partial-date rule after reviewing Gavia E4431-E4434. Those Form I-252 images show a typed month and year with no day between the month and comma. Three dated report versions alternated between preserving the missing day and supplying unsupported 2, 7 or 9; structural `OK` could not certify the reading. The master CSV rows have month/year but an empty collected-date field, and the assembled prompt deliberately excludes all CSV date columns. The observed failure is consistent with model completion of a familiar date layout or confusion with nearby marks; its internal cause is not observable.

The prompt now directs a slot-by-slot check: keep a genuinely partial date without a day, but retain a day when visible on another card. No semantic date rewrite, source-data change or validator heuristic was added. Existing reports remain historical output. Offline tests verify software behavior only; a future authorized fresh model run is needed to measure whether transcription accuracy improved. The changed prompt bytes intentionally change future cache fingerprints while preserving journal history.

## Conditional collector detail - 30 September 2026

Build and prompt **2026-09-30.1** move the full German/inset/translation/disclosure rule out of `BASE_PROMPT` into the existing CSV-selected `COLLECTOR_CONTAINS_PROMPTS["Steinbach"]` entry. The base retains one short sentence for a visible Steinbach collector when no applicable guidance was supplied. Shared side/retry requirements permit translation disclosures generically. Detailed instructions are included once only for matching enabled hints; existing collector matching and shared-record scoping remain in use.

The base prompt is 133 words / 855 characters shorter than build 2026-09-29.4; shared output requirements are also shorter. This is a text-size comparison, not a tokenizer or billing estimate. The changed base and assembled prompt bytes intentionally generate new fingerprints on future selected runs; existing reports and journal history remain intact. Both baseline and final offline suites ran **150 tests: 149 passed, one optional fixture skip**, including both mocked provider transports. No live requests or source-data changes were made.

## Steinbach German translation rule - 29 September 2026

Build and prompt **2026-09-29.4** add a reviewed José Steinbach edge case. When the collector is visibly Steinbach, or the relevant fallible CSV Collector value contains `Steinbach`, German source text is retained first and followed immediately by an English translation in parentheses. The rule explicitly includes inset or pasted notes on the main card, preserves uncertainty, excludes non-German names/localities/taxonomy, and requires the final disclosure `German text translated into English in parentheses.` only when a translation was supplied. That nonempty note intentionally produces `REVIEW` under the existing validator.

`egg_slip_prompt.py` retains exact-name `COLLECTOR_PROMPTS` for Brandt and adds the narrowly scoped `COLLECTOR_CONTAINS_PROMPTS` for Steinbach. Case and whitespace are normalized, matching guidance remains scoped to the applicable catalogue numbers on shared slips, and `--no-csv-hints` disables only the CSV-selected trigger; the conditional visible-name rule remains in the base prompt. Read-only catalogue inspection found 564 Steinbach rows, all currently `Steinbach, José`, including the five supplied records. The CSV remains evidence, not an instruction or authority over visibly conflicting card text.

Offline baseline: 148 tests, 147 passed and one optional fixture skip. Final: **150 tests, 149 passed and one optional fixture skip**, including both mocked provider transports. No live requests or source scan/CSV/report/journal/quota edits were made. The prompt change intentionally changes future cache fingerprints while retaining existing history.

## Active catalogue numbers and E8157 reading - 29 September 2026

Build and prompt **2026-09-29.3** tighten the cancellation rule after two fresh Spinus examples. E9551's red 9551 at upper left and E8157's blue 8157 above the printed heading are active numbers in the supplied images; the apparent strokes are not independent cancellation marks. A matching filename and fallible CSV hint support an active reading when no visual strike is present, but do not override a genuine cancellation. Only clearly struck-through catalogue numbers go in TRANSCRIPTION NOTES. The model is also asked to reread narrative adjectives letter by letter; the E8157 nest sentence reads “Nest very long and poorly built,” not “cosy.” No specimen-specific number or wording is hard-coded into the prompt.

The change touches prompt policy, version labels and documentation only. The offline suite ran 148 tests, with 147 passes and one optional fixture skip; both provider transports used mocks. Prior generated reports remain as historical output; no live model run was authorized or needed for offline verification. The existing prompt fingerprint naturally changes for future requests.

## Further specimen-reading refinements - 29 September 2026

Build and prompt **2026-09-29.2** refine the existing policy without changing validation or token accounting. Notes must not paraphrase fields or annotations. Genuinely cancelled catalogue numbers are retained once in notes, an explicit exception to the ordinary stamp-in-annotations rule. Word boundaries use visible strokes and egg/specimen context; field rules/borders are distinguished from actual cropping; routine punch holes are excluded; and scientific-name alterations must not cancel neighbouring common names or reverse the observed correction direction. No card-specific number was hard-coded.

The reported missing tokens were traced to older output: pasted CM1537 matches `Leucosticte_arctoa_transcriptions_20260923_1520.txt`. The September 29 11:31 report includes `TOKENS: 3,947 in | 97 out | 0 think | 4,044 total`. The current renderer always includes a token line, using `unknown` for absent legacy metadata. No usage repair was necessary; old reports remain untouched. The Linaria example identifies E3713, whose supplied-on-disk scan shows active Linnet and Carduelis cancelled with Acanthis above.

Baseline and final offline verification: **148 tests, 147 passed, one optional scan-fixture skip**. Both SDK transports were mocked; no live calls or source/report/journal changes. Prompt bytes intentionally change future request fingerprints; the previous edits remain in place.

## Concise annotations and review policy - 29 September 2026

Build and prompt **2026-09-29.1** address the maintainer's Accipitridae examples. `egg_slip_prompt.py` still owns reading policy: concise annotations, clearly evidenced cancellation only, optional necessary colour descriptions, no stroke/orientation/fraction-layout narration, no dirt-derived numeric punctuation, and short substantive notes. Calendar impossibility is strictly day/month validity, never breeding season, geography or presumed collector history. Crooked digits must be reread before claiming a source discrepancy. No specimen-specific readings were hard-coded.

`transcribe.py` removes the two field-format warning heuristics introduced in 2026-09-23.4. `bracket_warnings` exempts recognizable numeric printer codes immediately following numbered forms, retaining all text and continuing to flag uncertain code characters and other bracketed readings. Eligible matching cached entries get derived warning cleanup without changing response text, provenance or journal bytes. Other warnings and substantive model notes remain. The new prompt intentionally changes input fingerprints; the existing 48-hour cache limit and lock behavior are preserved. No responsibilities moved.

Verification: **148 offline tests, 147 passed, 1 expected skip** (optional original scan fixture not configured), including both mocked SDK transports. No live API calls or scan/CSV/report/journal edits. See [testing](testing.md) and [transcription policy](transcription_rules.md). Earlier format-review guidance below is historical and superseded.

## 48-hour cache reuse and lock cleanup - 23 September 2026

Build **2026-09-23.5** limits normal journal reuse to matching completed entries saved at most 48 hours ago. `Journal.recent` checks each entry's timezone-aware `saved_at` in UTC; invalid, absent, or future dates cause a fresh request. No journal history or readable reports are deleted. Test and console modes remain fresh by design; cache fingerprints and checkpoint ordering are unchanged.

On Windows, `species_lock` now uses a path-derived named OS mutex for both species and daily quota protection. It creates no lock file and removes an older `.lock` file for that path when safe on acquisition. A process crash releases the mutex. POSIX keeps persistent `flock` files because unlinking them would permit concurrent writers to lock different inodes. This is local-machine coordination, as before.

Offline baseline: **142 tests, 140 passed, 2 expected skips**. The focused cache-age and lock tests pass. Full-suite results appear in [testing](testing.md). No API requests, scan/CSV edits, commits, or pushes were made for this change.

## Fringilla fidelity and provenance update - 23 September 2026

Build **2026-09-23.4** implements the approved Fringilla review refinements. `egg_slip_prompt.py` remains the prompt owner and now exposes `PROMPT_VERSION`. Shared guidance emphasizes raised/multiline field attachment, character-by-character date/number checks, separate layers of alterations and filing notes, imprints, restrained explanations and distinct collector/owner/annotator roles. Signature candidates from this review were not hard-coded as facts or new collector aliases. See [review cases and unresolved readings](fringilla_review.md).

`transcribe.py` adds conservative field-format review hints without rewriting responses or adding API attempts. A side needs three recognized field starts before these heuristics apply; annotations/notes are excluded. Matching cached text receives derived format warnings locally without journal mutations. Bracket counts are labelled as passages, including legacy warning display, because source brackets are not necessarily uncertainty.

New results checkpoint request metadata (build/prompt versions, initial assembled-prompt SHA-256, existing input fingerprint, generation/image settings and hint enablement) before report output. Reuse preserves original provenance; older entries do not receive fabricated metadata. Returned model versions are shown when available. No provider execution, quota accounting or image ordering was extracted or replaced.

The maintainer chose **1.0** as the normal and test default for profiles accepting numeric temperature; Astra keeps omission and CLI overrides remain available. Test settings remain independent of normal profiles. Changed prompt/configuration bytes intentionally refresh selected requests, with existing reports/cache entries retained and the fingerprint algorithm unchanged.

Baseline: 133 tests, 131 passed, 2 skipped. Final: **142 tests, 140 passed, 2 expected skips** (POSIX lock on Windows and missing optional three-image fixture), including both SDK transport tests. Offline replay flags formatting in 7/7 records in each supplied Fringilla report. No API requests, source-data edits, commits or pushes. This verifies software behavior, not improved live transcription accuracy.

## Usage accounting and compact headers - 23 September 2026

Build **2026-09-23.3** adds the requested per-attempt tokens, paid-rate estimated USD, run totals/averages, and report footers. `token_usage.py` owns provider usage normalization, pricing and aggregation without egg-specific dependencies. `Transcriber.request` wraps the existing transports and records usage before OpenAI completion normalization or egg-slip validation; `_transcribe` retains pacing, persistent quota and retry policy. Each returned card result adds per-attempt `call_usage`, which normal journals checkpoint before report rendering. Existing final-response usage and cache identity remain compatible.

Headers now order ID, status, one consolidated review line, files, model, then tokens and cost on one line. The follow-up presentation change removes the separate COST line and estimated/USD/retry labels from displayed costs, including RUN summaries; accounting is unchanged. Provider prefixes are removed from model lines. Report finalization writes usage for that file even on a handled fatal stop or keyboard interruption; console totals cover the whole invocation. Reused entries retain historical metadata and add no fresh spending. Missing usage/rates are unknown; averages disclose the complete-usage sample count. No prompts, model settings, source scans, CSV, or validation semantics were changed in this pass. This adds one concrete shared accounting boundary, not general multi-domain support.

Offline baseline: **125 tests, 123 passed, 2 expected skips**. Final: **133 tests, 131 passed, 2 expected skips** (POSIX locking on Windows and absent optional sample fixture), including both SDK transports. Added coverage exercises retries, incomplete OpenAI output, cached-input discounts, reasoning, historical cache rendering, reuse spending, dated pricing and report scope; the interruption test now checks usage retention. Sandbox temporary-directory/write restrictions required elevated local offline commands. No live API calls, commit, or push occurred. Pricing assumptions and limitations are in [configuration](configuration.md#token-usage-and-estimated-cost); output conventions are in [transcription rules](transcription_rules.md#reports-and-ordering).

## Species-folder punctuation fix - 23 September 2026

Build **2026-09-23.2** strips trailing periods from the second scientific-name token used for folder routing, so CSV `Serinus sp.` resolves to `Serinus_sp`. CSV values and prompt hints retain their original spelling. General `safe_component` validation is unchanged; empty tokens and unsafe path characters remain errors. No source scans, CSV values, or folders were modified.

Offline verification: **125 tests, 123 passed, 2 expected skips**, up from the passing 122-test baseline. The real E2573 dry run succeeds. The requested range also exposes a separate missing JPEG folder for `Spinus_spinus`; that source-layout issue remains unresolved. No API requests were made. See [routing rules](filename_rules.md) and [verification](testing.md).

## Prompt module and fidelity update - 23 September 2026

Build **2026-09-23.1** implements the maintainer's explicit request to revise the prompt after reviewing sample outputs and move it out of the application. This is a deliberately behavior-changing prompt revision plus a narrow module extraction, not a claim of byte-identical modularization or a general transcription backend.

`egg_slip_prompt.py` now owns `BASE_PROMPT`, `COLLECTOR_PROMPTS`, `collector_instructions`, `build_prompt`, `output_requirements`, and `format_correction`. `transcribe.py` imports that module for initial requests and correction retries. Card/database models, discovery, image preparation, provider execution, validation, journals and rendering remain in the application. Type-only imports describe the existing card/database boundary without a runtime circular import or speculative interface.

The shared rules address the reviewed fidelity failures, including calendar anomalies and sex symbols. The former global Brandt signature candidate is now selected by the exact CSV Collector value `Brandt, Herbert W.`. Matching ignores case/whitespace; guidance is scoped to matched catalogue records, deduplicated for repeated matching rows, and disabled with `--no-csv-hints`. Other collectors use the base prompt until reviewed instructions are configured. See [customization and intentional cache migration](transcription_rules.md#editing-the-prompt-and-collector-guidance).

The full prompt already participates in cache identity, so this revision intentionally refreshes selected cards rather than reusing responses to the old prompt. Existing reports/cache entries are retained. No source scans, CSV, API settings, quota handling, validation or report conventions changed. No live calls were made; prompt quality improvements remain to be measured in an authorized comparison.

Baseline: 115 tests, 112 passed, 1 failed, 2 skipped. The existing repeated-test/cache fixture assumed temperature 0.1 despite the current test setting of 1.0; after resolving that, it also exposed a real-date versus fixed-date daily-counter reset. The fixture now chooses its temperature and fixes the clock for all runs, retaining the six-attempt accounting assertion. Final: **122 tests, 120 passed, 2 expected skips** (POSIX locking on Windows and the absent optional three-image fixture), with both SDK transports exercised offline. Windows sandbox access failures required running the suite and project writes outside the sandbox.

This update supersedes historical statements below that all prompt code remains in a single application module. Broader extraction still awaits a reviewed replay baseline.

## Windows implementation update — 22 September 2026

Build **2026-09-22.1** implements the requested `tests` target (`test` alias retained), reading `tests/inputs` beside the script and writing one `test_TIMESTAMP_MODEL_tTEMP.txt` report in `tests/outputs` beside the script. These defaults override the older Family-relative guidance below. The real curated set is now 10 cards / 18 images. No scans or CSV were renamed or edited, including the known wollweberi/ultramarina mismatch.

The initial Windows checkout actually contained build 2026-09-21.1, 103 tests, and no sample-test implementation despite the Work record below. Baseline: 101 passed, two expected skips. Current: 115 tests, 113 passed, two expected skips (Windows/POSIX lock test and the older optional three-image fixture). Both SDK transports ran offline; the actual curated dry run found 10 cards / 18 images. No live requests were made.

`run` now routes the sample folder through its existing processing loop, skips journals entirely, and durably writes each result to the combined report. Test temperature is resolved after the interactive target so normal runs retain profile defaults. Existing prompts, validation, image order, and normal fingerprint configuration are unchanged. No domain/backend extraction has occurred.

Profiles now include GPT-5.6 Luna, Terra, Sol, and **GPT-6 Astra** using one shared OpenAI Responses transport. Astra omits temperature automatically and rejects explicit numeric overrides. GPT-5.6 tests can pass the test temperature; use `--temperature auto` for initial comparisons because numeric parameter acceptance is not proven by offline transport tests. See [configuration](configuration.md) and [testing](testing.md).

The remainder preserves the earlier Work handoff and its historical verification claims; where they differ, this update and current code/tests take precedence.

## Purpose and context

The current program transcribes scanned historical museum egg-collection slips. The working collection has roughly 10,000 physical slips / 12,000 images, many form types, old scientific names, cursive and pencil, crossings-out, stamps, marginal additions, and occasional narrative backs. A physical slip can refer to several catalogue records; an image is not necessarily a whole record. A previously reported production CSV load contained 10,174 catalogue numbers across 10,190 data rows. Those are historical observations, not counts of data bundled here.

The maintainer works with these records and developed the initial program with Gemini, partly because ChatGPT was unavailable at work. Work revisions concentrated on input correctness, fidelity, resumability, explicit failure handling, and eventually repeatable model comparisons. The model reads the scan; the surrounding software protects ordering, selection, evidence, progress, and accountability. No public accuracy benchmark was established by the offline tests. User impressions of excellent accuracy should not become a measured performance claim.

The longer-term intent is a reusable system for other museum records, field notes, expedition documentation, handwritten forms, catalogue cards, and repeated archival series. Egg slips are the first and only implemented domain. The immediate objective is clean separation of existing responsibilities; immediate multi-domain support is not required.

## Authority and documentation map

**Current code + current tests = implementation truth. Conversation history = rationale and observed edge cases. Documentation = their durable bridge. Architectural intent = direction, not current functionality.** If these disagree, inspect the code, preserve working behavior, and update the relevant document explicitly.

| File | Role |
| --- | --- |
| [README.md](../README.md) | Public overview, setup, commands, honest current scope. |
| [AGENTS.md](../AGENTS.md) | Concise durable operational instructions for coding agents. |
| This handoff | Execution map, decisions, limitations, invariants, and future extraction plan. |
| [docs/filename_rules.md](filename_rules.md) | Authoritative human explanation of current CSV, targets, paths, filenames, and grouping. |
| [docs/configuration.md](configuration.md) | Current profiles, key loading, API adapters, pacing, quotas, and retries. |
| [docs/transcription_rules.md](transcription_rules.md) | Current egg-slip SOP, validator boundaries, statuses, reports, and cache semantics. |
| [docs/testing.md](testing.md) | Offline verification, real-image fixture, live comparisons, and baseline strategy. |
| [transcribe_notes.md](transcribe_notes.md) | Preserved revision history; older instructions are superseded where noted. |

Do not duplicate an entire rule table across documents. Update its focused document and link it from overview/handoff material. Prompt changes must update the actual executable prompt, not just prose documentation.

## Historical Work snapshot and verification - 22 September 2026

The following records the original Work environment, not the current checkout. The authoritative implementation for this pass was the current Work `transcribe.py` and `test_transcribe.py`, not the public GitHub version. Their SHA-256 values are recorded to make this snapshot unambiguous:

```text
transcribe.py       85b1e15887b6ee9ab7eacec15a783443012690a07f466a0d365f4743766bcea3
test_transcribe.py  4d31171e7ad85add4f6552f953499762216648d01ca223f11ef640be3ae2a7f6
```

The public checkout used only as the repository/layout baseline was commit `48874132da9696189a22bdcfad1c66f3b4d85b06` (`main`, 20 September 2026). It contained `.gitignore`, the script, tests, and revision notes; all three Work files were newer/different. They were overlaid onto the checkout before documentation work. Consequently a Git diff against that commit includes **pre-existing application/test changes**. Those are not new functionality authored by this handoff task. No commit or push was made, and the maintainer's actual Windows checkout/unpushed diff was not available for direct inspection.

Working capabilities include normal species/exact-number/CSV-row selection, both supported folder layouts, shared slips, ordered multiple sides, front-only inputs, explicit uncatalogued groups, conservative prompt rules, output/status validation, durable journals, model profiles, persistent daily counters, bounded service/format retries, an optional OpenAI adapter, and independent mixed-species model/temperature tests.

Baseline and final post-documentation verification each ran **115 offline tests, all passing with zero skips**, using both installed SDKs and the original three-image fixture. A separate fresh-checkout-style run without the optional image directory discovered 115 tests: **114 passed, one expected sample-fixture skip**. Documentation links/anchors, CLI option names, ignore rules, whitespace, and credential-pattern checks passed. The application and test-file hashes above remained unchanged. The environment and exact commands/skip conditions are in [testing](testing.md). No live requests were made. The application version remains unchanged because this pass does not change its behavior.

Newly prepared documentation/configuration includes the README, this handoff, concise agent instructions, four focused docs, direct dependency pins, a blank credential example, ignore rules, and input/output folder READMEs. The previous revision notes are retained verbatim below a supersession notice. No source photographs, catalogue export, credentials, generated results, or quota state were added.

The maintainer will add a hand-selected 10–15-card sample set before Codex takes over. Earlier individual attachments were available in Work, but they were not automatically promoted into that set. A full production catalogue, reviewed golden transcriptions, quantitative model comparisons, Windows/Drive integration results, and account-specific live access evidence are not part of this repository snapshot. Missing samples are expected, not a reason to fabricate them or block documentation.

## Likely development sequence

1. Continue the established Gemini production workflow and review records against their source scans.
2. Curate a small reviewed baseline from existing reports and supplied scans; capture deterministic request/response fixtures without new paid provider comparisons.
3. When extraction is requested, separate remaining egg-specific configuration, discovery/parsing/grouping, validation, and output from reusable execution machinery.
4. Check each step against offline tests and frozen prompt/image/cache/output expectations.
5. Continue focused egg-slip improvements, keeping prompt or quality changes separate from architectural moves.
6. Consider a second archival collection only when a real use case calls for it.

This roadmap does not authorize live requests or an unsolicited refactor. Additional Gemini spot checks can be useful when specifically requested; they are not a substitute for deterministic replay during behavior-preserving extraction.

## Architecture: current execution flow

There are three runtime modules: `transcribe.py`, the egg-specific `egg_slip_prompt.py`, and the domain-independent usage/accounting module `token_usage.py`, plus the standard-library `unittest` suite `test_transcribe.py`. There is no package/domain registry, database server, graphical UI, background worker, or concurrency pool. Numbered source comments identify nine broad sections. Imports do not call APIs; SDK/image imports are mostly delayed until needed.

| Phase and actual symbols | Current behavior | Boundary observation |
| --- | --- | --- |
| `main`, `parse_args`, `configure_model_profile`, `ModelProfile` | Resolve CLI/profile defaults and interactive alternate-model selection; print build, script, interpreter, selected limits. `--version`, `--help`, `--list-models`, and `--check-config` have early paths. | CLI combines execution settings with museum paths and test orchestration. |
| `run`, `load_database`, `Database` | Load CSV before the target prompt; index E-numbers, row numbers, species/family mappings, retaining duplicate rows. | Strong egg-slip assumptions; even test mode requires a CSV. |
| `select_targets`, `enum_species`, `species_name` | Resolve species, exact E-number with optional `*`/`!`/`@` mode, or inclusive row selection. `test` is recognized separately in `run`. | Domain selection and generic run mode are intertwined. |
| `resolve_folders`, `child_directory` | Find exactly one JPEG directory using CSV family/species mapping and either supported layout. | Source organization policy, not engine policy. |
| `discover_cards`, `side_number`, `Card` | Parse JPEG names; group physical slips; order/label sides; collect file warnings; append uncatalogued groups. Test mode adds unmatched-CSV warnings. | `Card.enums` and literal FRONT/BACK labels make the record object domain-specific. |
| `missing_catalogue_numbers`, `missing_collection_date`, `missing_output_block` | Identify selected catalogue entries absent from JPEG filenames and render current CSV-only blocks in numerical order. | Egg-specific fields, dates, and output; bypasses provider requests and transcription journals. |
| `egg_slip_prompt`: `build_prompt`, `output_requirements`, `format_correction`, `BASE_PROMPT`, `COLLECTOR_PROMPTS`, `COLLECTOR_CONTAINS_PROMPTS` | Assemble reading rules, exact-name and reviewed-containment collector guidance, actual side requirements, warnings, shared-record references, and optional CSV hints. | Extracted egg-slip prompt policy; structural validation remains in `transcribe.py`. |
| `prepare_image`, `prepare_card` | Decode JPEGs; preserve bytes if possible; apply EXIF orientation/optional resize in memory; calculate payload estimate and a SHA-256 fingerprint; construct ordered labelled request parts. | Image handling is reusable; labels/manifests and Gemini-shaped parts mix other concerns. |
| `species_lock`, `Journal`, `open_output_report` | In normal saved mode, acquire a species lock, open journal and new report before spending requests. Test and individual fresh-report modes open a report but never a journal; all-missing normal selections also skip the journal. | Generic safety primitives have domain naming/storage and success policy embedded. |
| `Journal.reusable` | Accept latest matching `ok`/`review` entry within 48 hours; derive empty-note and obsolete-layout/bracket-warning cleanup locally. | Storage code knows domain statuses and section headings. |
| `Transcriber.ensure_client` | Lazy provider import, key lookup, explicit endpoint, timeout, SDK retry disabling. No credential is requested for all-cache reuse. | Mostly reusable; key search still depends on CSV/Family settings and `__file__`. |
| `RateLimiter`, `DailyQuota`, `Transcriber.transcribe` | Pace, reserve quota, issue request, normalize OpenAI, validate, correct format once, retry service errors within budget, classify failures/stops. | Core execution directly invokes egg-specific validation and retry instructions. |
| `Transcriber.request`, `token_usage` | Record per-attempt usage before response normalization/validation; normalize tokens, estimate costs, aggregate card/report/run totals. | `token_usage.py` has no egg-specific dependencies; the existing request lifecycle supplies attempts. |
| `validate_response`, `section_headers`, `notes_have_content` | Exclude thought text, check completion/sections/plain-text constraints, derive warnings and token usage. | Provider completion validation and egg-slip grammar share one function. |
| `Journal.append`, `durable_write`, `output_block` | Save a new result durably before readable report text; render CM/file banners/status/reviews; preserve failed answer text. | Journal durability is reusable; rendering/status interpretation is largely domain policy. |
| `run` cleanup/exit | Close client, retain completed writes, print totals, stop on fatal errors/quota, return nonzero on failures/discovery issues. | Job lifecycle remains mixed with species report aggregation and test footers. |

`--dry-run` performs CSV/routing/group discovery, lists sides and selected missing-card entries, without image decoding, API/key lookup, journals, reports, quota files, or folder creation. It can reveal names/order issues but does not establish scan integrity or credentials.

Console-only normal runs make fresh API calls with no report or transcription journal. They still write the persistent quota state/lock. This supersedes early chat/notes statements that console mode writes no files at all.

Test mode routes every recognized card in one flat directory through the same parsing/prompt/image/provider/validation machinery. It skips production folder lookup, marks missing CSV references for review, uses `TEST_TEMPERATURE` unless explicitly overridden, and writes one model-tagged report. It never opens a `Journal`, even if production cache entries would match. A restart after a partial test starts at the first card again.

Exit code 0 means no recorded failed/paused/discovery issues; accepted review results do not make the run fail. Code 1 covers run failures, missing/ambiguous files/routing, quota pauses, or an empty test set. Keyboard interruption returns 130. Argument-parser errors use argparse's code 2. A fatal stop can happen before the final totals/footer, so read the actual messages and report termination state.

## Configuration and model system

The exact profile table, parameter precedence, lookup paths, and retry rules are maintained in [configuration](configuration.md). Important orientation points:

- Current default: `gemini-3.5-flash-lite`, temperature 1.0, high thinking, 15 RPM / 500 local daily attempts. Configured `gemini-3.6-flash` and `gemini-3.8-flash` use 5 RPM / 20 daily attempts. These were the maintainer's allowances, not general provider guarantees.
- Optional OpenAI profiles share one implemented Responses adapter and 5 RPM / 20 local test caps. The three GPT-5.6 profiles use temperature 1.0; Astra omits it. They remain available in code, but the maintainer does not want paid comparison runs. A configured entry is not proof of account access.
- `MODEL` chooses the entire profile. Unknown IDs fail locally. A model switch should not accidentally retain the previous model's timing or generation options.
- Test temperature is a separate code setting immediately below model selection; an explicit CLI temperature wins. Supported profiles inherit `TEST_TEMPERATURE=1.0` for test mode unless explicitly overridden; Astra omits temperature automatically. `--temperature auto` omits it for other profiles too.
- Gemini and OpenAI receive the same evidence/instructions, with provider-specific serialization and generation options. Both clients disable their hidden automatic retries so the script controls and accounts for every call.
- Daily state persists beside the script by default and is shared across normal/test/console runs and restarts. It is keyed by provider/model, not key/project. It is not a server quota meter or distributed scheduler.
- A 503 means service unavailable; it does not prove the daily cap was reached. The reported “one card then 503” motivated better configuration and bounded waits, not a fabricated diagnosis.
- One invalid-response correction is allowed within the total per-card request budget. Service failures may consume other attempts. Token cutoffs are retained as failures; they do not trigger an endless retry with the same cap.
- Keys come from a local `.env` search before process variables, using a built-in key-only reader. Automatic hidden prompting was removed; `--prompt-key` makes manual entry explicit. `.env` lookup success is not authentication success.

The code has a dated Gemini 401 migration hint inherited from troubleshooting. It should be treated as historical provider guidance and checked against current official documentation if that error returns. The exact cause of the maintainer's earlier rejected credential was not established. Do not promise that an `.env` change repairs an API-rejected key.

The CSV defaults to its named export beside the script; the Family root retains the maintainer's Windows path. Moving `transcribe.py` changes its default `.env` and quota-file location: deliberately retain or point `--quota-file` to the existing state. Do not use a new counter to pretend earlier requests never happened. No live credentials or source catalogue were needed for this documentation pass.

## Input and filesystem conventions

[Filename rules](filename_rules.md) owns the complete grammar and selection table. The essentials to retain during extraction are:

- Real scans live under a CSV-derived family/species directory, optionally with a genus directory, then `JPEG`. Only direct JPG/JPEG files are read. Folder matching is case-insensitive and rejects ambiguity.
- The master file is a CSV export with exact `catalogNumber`, `Scientific Name`, and `Family` headers, not arbitrary project spreadsheet columns or `.xlsx` parsing. Other museum graphing/indexing tools discussed elsewhere are not part of this repository.
- `_E<digits>` tokens identify records; every number in a shared filename can select the group. Leading zeros remain meaningful. Multiple E-numbers do not mean multiple copies of the same physical scan/request.
- A/B or numeric side suffixes identify ordered images; unlettered/A is front. Lone fronts are normal; missing fronts/gaps are warnings; duplicate sides are errors.
- `_exchanged` is accepted after the optional side suffix and excluded from group identity, while original filenames remain in output. Other arbitrary suffixes are not quietly accepted.
- Explicit `Uncatalogued`/`Uncataloged` patterns permit scans absent from the sheet. Species and visited row-range folders include them; exact E-number targets do not. They appear after numbered groups.
- `E123*` means one fresh console-only E-number reading, **not a wildcard**. `2-1000` means CSV row numbers, **not an E-number range**.
- Test paths default to `tests/inputs` and `tests/outputs` beside `transcribe.py`, independent of the Family setting and launch directory. Explicit path overrides remain available.

All of these selection/record/folder rules are domain behavior. Safe path checks, image decoding, in-memory transforms, file locks, and durable writes are potential reusable mechanisms. Even image discovery has two parts: generic filesystem enumeration and domain-specific admissible paths/names/grouping. Avoid placing the latter in a supposedly generic loader.

## Prompt and transcription architecture

`BASE_PROMPT` and prompt assembly live in `egg_slip_prompt.py`. `build_prompt` appends `output_requirements(card)`, file warnings, multi-number references, and JSON catalogue hints for each matched record. Missing and uncatalogued records receive no invented reference values. `--no-csv-hints` is an ablation option, not a no-CSV execution mode.

`prepare_card` places a filename and explicit section label immediately before each image. The model is told how many front/back images were actually supplied and which back headings are expected, so a generic template cannot require a nonexistent back. The format retry adds a correction to the original evidence; it does not use the faulty answer as source truth or mutate the original request contents.

The detailed SOP is in [transcription rules](transcription_rules.md): visible collection headings first; dynamic `Label: value`; separate stamps/fields; original spelling/units; carefully scoped ditto expansion; readable brace-group dimensions; plain fractions; uncertain/inferred readings in brackets; meaningful annotations; one final notes section; all supplied sides. These are primarily domain rules, not universal archival grammar.

The hand-written Hanna sample supplied a formatting model, not permission to modernize or normalize every word. The user later corrected a collector reading on a difficult Brandt slip to H. W. Brandt. The prompt permits that candidate only when visible strokes and context support it, rather than unconditionally substituting collection ownership for collector identity.

Prompt policy has already been extracted to `egg_slip_prompt.py`. The eventual backend boundary should accept the assembled domain prompt and validation/correction policy. Further behavior-preserving moves must retain the prompt **byte for byte**: even a whitespace change changes its fingerprint and may spend quota retranscribing every selected normal card.

## Output architecture and review philosophy

[Transcription rules](transcription_rules.md#reports-and-ordering) owns the exact report, banner, section, spacing, and cache conventions. In brief, normal runs write one report per visited species in its family folder, with matching successful journal reuse. Test runs write one independent mixed-species report with model/temperature suffixes and no journal. Both use minute timestamps with collision counters, UTF-8, durable incremental writes, and retained failed answer text.

`output_block` knows CM labels, catalogue-number lists, filename banners for uncatalogued material, model/source metadata, review lines, and two blank lines. This is egg-slip rendering. `open_output_report` and `durable_write` contain reusable file safety, but the calling code supplies domain naming/location/aggregation. Another domain should eventually choose its own renderer and storage plan without reimplementing fsync/collision handling.

`OK` is structurally accepted, not human-verified. `REVIEW` is accepted with warnings and is reusable normally. `FAILED` and `PAUSED` are not completed cache results. “Annotations” are artifact content; “transcription notes” explain reading/physical problems. Empty/None notes do not imply a problem. The bracket heuristic counts bracketed passages, with narrow exemptions for `[blank]` and recognized printed form codes; other literal source brackets can still trigger review.

Provider completeness checks should eventually be generic. The presence/order of ANNOTATIONS/BACK OF SLIP/TRANSCRIPTION NOTES, CM banners, specific note sentinels, and uncertainty interpretations should be domain policy. Success/storage should not require a generic journal to understand an egg-slip heading, as `Journal.reusable` currently does for the legacy notes fix.

## Important invariants

1. Source scans and the master CSV remain read-only. Orientation/resizing happens in memory. Never delete/rename source data to make a parser test pass.
2. One physical card's images remain together, ordered and explicitly labelled, including shared catalogue slips. No duplicate submission just because multiple selected E-numbers match it.
3. A front-only card is valid. A supplied back cannot disappear; a lone back cannot be silently called a front. Duplicate-side ambiguity must remain visible.
4. Retain explicit uncatalogued material in its current selection scopes, with filenames instead of invented catalogue banners and no unrelated hints.
5. Preserve historical wording, uncertainty, and meaningful marks. Do not turn interpretation into unmarked certainty or allow catalogue references to override visible text.
6. Never discard substantive unexpected response text just to satisfy the expected schema. Available failed/partial answer text remains inspectable. Do not expose model thought text as transcription.
7. Preserve public output syntax/order/spacing and downstream compatibility unless a change is requested and documented. Tolerant heading recognition is deliberate, not a reason to relax real completeness checks.
8. Normal results are reusable only for matching relevant inputs/settings; failed/paused results are not successful cache entries. Preserve compatible Gemini cache identity during extraction.
9. Test runs make independent requests and never read/write transcription journals. Test temperature and orchestration must not change normal temperature, output, or resume behavior.
10. Every attempted provider call passes pacing and persistent reservation, including formatting/service retries. SDK retries remain disabled. Never silently reset damaged quota state or switch models.
11. Normal results are flushed/synced to the journal before readable report writes. Transient failures must not erase completed work; output filename collisions must not overwrite earlier reports.
12. Runtime defaults are explicit. Changes in module location must not silently change `.env`, quota-file, input, or output locations. Do not claim cross-machine locking or real-time provider quota knowledge.
13. Refactoring changes ownership of responsibilities, not transcription semantics. New reusable code should acquire no new egg-specific assumptions without a concrete reason.
14. Keep real credentials, source collection bulk data, generated reports, and sensitive metadata out of the public repository. A selected public image set requires deliberate publication review.

## Edge cases discovered

The table records classes of cases, not a specimen-by-specimen transcript. “Domain” means the future egg-slip layer; “core” means reusable mechanism or provider execution.

| Case and why it matters | Current handling | Remaining risk / future owner |
| --- | --- | --- |
| Directory order can present B before A. | Sort side numbers, explicitly label each image, send the whole group in one request. | Wrongly labelled original files still need human correction. Domain grouping + core order preservation. |
| Most cards have no back; a generic output template invented one. | Actual side-count prompt; harmless empty unexpected back placeholders removed with review. | Substantive unexpected back text fails rather than being dropped. Domain validation. |
| Valid response used `SECTION: BACK OF SLIP` without colon (reported E4936). | Recognize standalone heading variants, preserve text, still require expected side sequence. | New exotic headings may fail; do not replace with strict colon-only checks. Domain. |
| Front and back each have annotations; one side repeats the heading. | Per-side annotations allowed; same-side repetition retained with review. | The reported E4933 response was not supplied; the pasted E15 example was a different card. Do not invent an exact diagnosis. Domain. |
| Notes say `None.` but old output said notes were present. | Empty sentinel detection, including cached-warning correction without paid rereading. | Old reports remain unchanged; literal brackets can independently cause REVIEW. Domain normalization in generic journal is debt. |
| Printed bracketed form code looks like uncertainty. | Recognized numeric printer codes after numbered forms are preserved without a review flag. | Other literal source brackets can still trigger review; uncertain form/code characters must remain flagged. Domain policy. |
| Shared E186/E187-style slip is selected through its second number. | Full-token matching across all numbers, one group/request, separate hints and banners. | Different prefixes/base IDs with the same number can still be separate groups; no cross-folder deduplication. Domain. |
| A/B plus unlettered front, or `_exchanged` duplicate. | Reject ambiguous group; tag itself is recognized and not another side. | Do not choose a scan arbitrarily. Domain parsing. |
| Missing front, numeric suffix gap, or extra supplied sides. | Keep back-only identity, warn gaps, number supplied back sections in order. | Side count is not proof an unknown missing scan exists. Domain. |
| Uncatalogued scans are absent from the spreadsheet. | Explicit filename grammar, normal side handling, last in relevant report, filename headers. | Species routing still needs a family mapping; arbitrary unrecognized filenames are not accepted. Domain. |
| Filename E-number missing from CSV. | Species mode reads the image without hints; test mode also adds a review flag. Exact-number targeting needs a CSV row to route. | Normal-mode missing-reference warning is not equivalent to test mode. Domain limitation. |
| Duplicate catalogue rows or two valid folder layouts. | Retain duplicates; reject conflicting routing; require exactly one JPEG directory. | No automatic reconciliation of real catalogue errors. Domain metadata. |
| Difficult signature with useful contextual clues. | Permit supported Brandt candidate/inference, bracket unresolved inference, explain it. | No live improvement measurement; collection heading alone cannot identify collector. Domain prompt. |
| Printed braces mix diameter/depth columns; ditto marks repeat labels. | Prompt keeps parent/subfields together, permits clear within-column expansion. | Python cannot verify semantic alignment; inspect outputs. Domain prompt. |
| Model emits LaTeX for fractions or stacked measurements. | Detect known math syntax, one corrective rereading of images, preserve failed text. | Regex is not a complete Markdown/LaTeX parser; never “simplify” uncertain stacked values automatically. Domain format policy + core retry mechanism. |
| Blank supplied back versus missing response text. | `[blank]` is valid for a supplied back; an empty back section fails. | A model could falsely call writing blank; requires image review. Domain. |
| Empty answer, refusal, thought parts, or output-token cutoff. | Answer-only extraction/completion checks; failed text retained; no success cache. | Structural checks cannot prove all source lines were read. Core completion + domain validation. |
| Credentials beside script but VS Code starts elsewhere. | Script/project-aware `.env` lookup before stale environment, source diagnostics, explicit optional prompt. | API validity is separate; rejected key cause was not confirmed. Core credentials + domain path defaults. |
| Retry/503 or 20/day model appears to hang after switching. | Complete profiles, visible attempts/waits, bounded backoff, daily cap/long-delay pause. | TPM, outside traffic, account limits, and service load remain outside local control. Core. |
| Interrupted report write after a successful paid response. | Journal first, then fsynced report; matching normal restart reuses it. | Crash before journal append can repeat a request; test runs intentionally have no reuse. Core persistence. |
| Partially written journal line or damaged quota file. | Journal preserves/ignores damaged entries; quota corruption stops conservatively. | No journal compaction/repair UI; preserve evidence rather than silently reset. Core with domain reuse policy. |
| Repeated tests with identical settings hit production cache or overwrite results. | Test never opens Journal; exclusive model/temp/minute filenames with counters. | No automatic sweep, subset, test resume, or complete run manifest. Core test lifecycle + domain report conventions. |

## Major decisions and why

**Group sides into one request.** Front/back narratives, annotations, and corrections belong to one physical artifact. Keeping them together provides shared context and one result while deterministic labels avoid role reversal. Counting images as separate cards would fragment evidence and distort quota planning.

**CSV is a hint, not ground truth.** The original prompt called reference values “GROUND TRUTH,” encouraging replacement of historical readings with modern catalogue text. The source image wins; separate hints assist difficult visible letters and can be disabled for comparisons. Duplicate rows are preserved because overwriting them hides conflicts.

**Use dynamic fields and conservative plain text.** Forms differ across collectors and eras. A fixed field schema would lose or invent information. The human SOP requested readable labels, visible headings, aligned CM banners, clear dimensions/ditto expansion, and space between slips—not automatic modernization. Python enforces mechanical headers/spacing; reading/layout interpretation largely remains a prompt task.

**Show uncertainty and retain failures.** Plausible guesses are especially dangerous in museum data. REVIEW signals work for a human rather than falsely claiming completion quality. FAILED can still contain much useful text: status reflects validation/request state, not a count of recovered words. Saved responses preserve evidence of problems for repair.

**Tolerate harmless headings, enforce real sides.** Earlier strict spelling/colon/global-annotation checks rejected complete readings and wasted requests. Tolerance was added for those cosmetic variants while missing, duplicate, empty, or misordered supplied backs still fail. Empty invented templates are the narrow exception that can be removed; substantive text is preserved.

**Retain uncatalogued records.** Absence from a spreadsheet does not make a museum artifact unworthy of transcription. Explicit naming keeps discovery predictable, filename banners avoid invented catalogue numbers, and appending them preserves the readable order of numbered records.

**Separate service and malformed-response handling within a shared ceiling.** An outage can resolve with pacing/backoff; repeating the same formatting mistake five times is often wasteful. A single correction uses actual side instructions and plain-text requirements, with no bypass of total attempts or quota accounting. The old log “Attempt 1/5 … retry … FAILED” was confusing because these limits differed; logging now describes the correction explicitly.

**Centralize model settings and disable SDK retries.** Models available to the maintainer had substantially different request allowances. One selector should change timing/timeouts/attempts together. Hidden SDK retries would escape the script's counter and pacing. Persisting local daily counts across restarts is conservative protection, not a replacement for provider quota enforcement.

**Keep the established production choice.** Flash-Lite's request allowance made large batches practical, and the maintainer is satisfied with its current readings. The earlier temperature 0.1 setting was superseded by 1.0 on 23 September; high thinking became the Flash-Lite default on 5 October. On 7 October the maintainer chose to continue with Flash-Lite without paid GPT comparisons. This is an operating decision, not evidence of universal superiority or a measured cost/accuracy ranking.

**Preserve original image detail and journal exact inputs.** Automatic 2,000-pixel shrinking was removed as the default so optional resolution loss is explicit. Orientation/resize changes operate on copies in memory. Fingerprints include what was actually sent, avoiding stale reuse after a scan or prompt changes. The original Gemini manifest shape was deliberately preserved when provider profiles were added.

**Bypass caches for comparisons, retain them for production.** Reusing a prior answer invalidates a model/temperature experiment. Test mode always rerequests, including after interruption. Normal mode avoids new requests for matching completed work within its 48-hour reuse window. Changing only rate settings should not invalidate that work.

**Checkpoint before readable output and avoid collisions.** Users need completed work to survive interruptions and text-write failures. Journals are synced first; minute timestamps remain readable and counters preserve repeat runs without seconds/microseconds or accidental appending.

**Separate domain rules before growth, but do not build a framework.** Egg-specific assumptions are already spread through orchestration, credentials/path defaults, validation, retry correction, cache normalization, and rendering. Extracting those existing responsibilities reduces future edit risk. Without a second collection, a rich generic plugin/schema/workflow design would be speculation. A real second source should test the abstraction later.

Rationales above come from this conversation and preserved revision notes. No established rationale was available for every constant (for example the exact 16,384 output cap); such values are documented as current defaults rather than invented design conclusions.

## Things tried and changed

| Earlier approach | Useful lesson / replacement |
| --- | --- |
| Unsorted directory listings; match first E-number only. | Explicit side ordering/labels and all-number group matching. |
| Embedded credential and environment-only lookup. | No committed credential; key-only `.env` loader, stable search roots, explicit Developer API backend, manual prompt only on request. The original attached script had a key; rotation is not verifiable here. |
| Reference catalogue called ground truth. | Fallible hints with source precedence and no-hints testing. |
| Always expect a back; require one global ANNOTATIONS heading. | Actual side expectations and per-side annotation handling. |
| Require `BACK OF SLIP:` exactly. | Accept observed `SECTION:`/colonless variants while validating actual structure. |
| Any nonempty notes string means review. | Empty sentinel interpretation and local cached-warning correction. |
| Treat all unknown filenames as excluded. | Add a specific uncatalogued grammar and the requested `_exchanged` tag; keep other unexpected filenames visible. |
| Literal brace/column interleaving and unsupported signature guesses. | Prompt-level grouping and evidence-backed signature interpretation; never blanket-correct names or dimensions. |
| LaTeX representation accepted as ordinary text. | Bounded format correction using images; no destructive equation postprocessing. |
| Every launch requests every image again; write errors indistinguishable from transcription. | Exact-input journals, explicit statuses, failure text retention, normal restart reuse. |
| Automatic 2,000-pixel cap and simple fixed sleeps. | Original-resolution default, optional resize, request-start pacing and bounded error-specific backoff. |
| Seconds/microseconds in output timestamp. | Hours/minutes with safe collision counters, per maintainer preference. |
| Hand-edit separate model/rate settings; SDK retries hidden from counter. | Profiles, persistent attempt reservations, visible pauses, disabled SDK retries. |
| Ad hoc console runs for comparisons. | Flat mixed-species test input, independent reports, test temperature and model suffixes, guaranteed application cache bypass. |

The September 18 signature/layout/plain-text prompt update intentionally changed normal cache keys. September 21 profile/test-mode updates preserved the default normal Gemini prompt/configuration keys. Cosmetic output and back-heading parser fixes did not inherently invalidate successful cached work. Do not assume every script version bump should force all transcriptions again.

## Known issues and technical debt

| Classification | Current issue / implication |
| --- | --- |
| **Remaining review limitation** | Literal bracketed print outside the recognized form-code and `[blank]` exemptions can still cause REVIEW. Counts are labelled bracketed passages; no full source/editorial provenance distinction exists. |
| **Known limitation** | Structural validation cannot detect every omission, incorrect word, false blank back, invented field, or misassigned dimension. The plain-text prompt is stronger than the implemented Markdown checks. |
| **Known limitation** | Existing manual/reference reports have not been established as a complete, versioned gold set with a repeatable accuracy metric. Request provenance and per-attempt token/cost estimates are implemented; a full replay manifest and automatic accuracy scoring are not. |
| **Known limitation** | CSV + folder assumptions are required for normal routing; test still requires a readable compatible CSV. No `.xlsx`, PDF, TIFF, arbitrary recursive discovery, or cross-folder physical-card deduplication. |
| **Known limitation** | The special unmatched-CSV review warning exists only in test mode. Front-only species scans absent from CSV still run if their species folder can be routed. |
| **Known limitation** | No automatic comparison sweep or partial-test resume/subset selector. A repeat test spends requests again from the start; a low daily allowance can make large comparisons awkward. |
| **Design tradeoff** | Original-resolution input can exceed the conservative shared 19 MB inline budget. Optional resize is available; no upload/file-service path exists. |
| **Design tradeoff** | Persistent attempt counters are conservative, per provider/model/state file, and unaware of other tools/accounts/machines. No TPM limiter, distributed rate control, or concurrency implementation exists. |
| **Design tradeoff** | Append-only journals can grow; latest entry per key wins. A failed forced reread can supersede an earlier success for automatic reuse. A crash before checkpoint still permits repeated cost. |
| **Architectural coupling** | `run` handles selection, CSV/domain routing, test mode, generic execution, journal policy, report aggregation, and output. `Transcriber.transcribe` hard-calls domain validation and correction instructions. |
| **Architectural coupling** | `prepare_card` returns Gemini-shaped content; OpenAI normalizes back to a Gemini-shaped completion object. `generation_config` and test temperature rely on a large shared argparse namespace. |
| **Architectural coupling** | `Journal.reusable` parses egg-slip notes to fix a historical warning; `species_lock` is reused as a generic quota lock despite its name. `Card` and `output_block` know E/CM/side/uncatalogued semantics. |
| **Architectural coupling** | `load_api_key` searches domain CSV/Family directories; script `__file__` determines credential and quota locations. A naive module move could change effective configuration without changing CLI flags. |
| **Verification gap** | Windows mutex behavior has offline coverage and some production selections were checked read-only. Cross-machine Drive coordination is unsupported. Live API compatibility, provider quotas, and measured handwriting/signature accuracy were not established by this documentation pass. |
| **Test infrastructure tradeoff** | Optional SDK/scan tests skip when unavailable; the original-image test expects exactly three specific matching JPEGs. Curated live samples are not yet a deterministic baseline. Several tests import a monolithic `transcribe` facade, constraining first extraction. |
| **Repository hygiene** | The README declares Apache License 2.0, but a standalone licence file is absent. Collection-material rights and the historical exposed-key rotation are not established by this documentation pass. Existing tracked reports remain tracked despite ignore rules; review staged content before publishing. |
| **Future ideas, not requirements** | A second document domain, better uncertainty provenance, a full replay manifest, reviewed response fixtures, and eventual concurrency can be considered after baseline/extraction work. Token/cost reporting already exists. |

Do not fold these into this documentation task as surprise functional changes. If a later task addresses a bug, distinguish the intentional behavior change from a behavior-preserving extraction.

## Architectural direction: reusable backend versus domain layer

**Current:** `transcribe.py` contains most domain and execution behavior with two provider paths; prompt policy is in `egg_slip_prompt.py` and usage accounting is in `token_usage.py`. **Intended:** a small collection layer supplies record discovery/grouping, metadata, prompt, validation, and rendering; execution infrastructure handles requests and safe result lifecycle. Neither a generic domain interface nor a `core/` package exists yet.

| Responsibility | Likely home and seam based on current code |
| --- | --- |
| Paths, required CSV/hint columns, species/family routing, filename regexes, `Database`, E-number grouping, side labels, uncatalogued scope/order | Egg-slip domain. Begin by extracting these existing policies, not imposing them on a universal record schema. |
| `BASE_PROMPT`, `build_prompt`, `output_requirements`, note sentinels, section grammar, uncertainty/review interpretation | Egg-slip domain. Distinguish generic completion failure from domain format failure; the domain can generate its correction instructions. |
| `output_block`, CM/file banners, per-species aggregation/naming, report destination, test filename tags as chosen presentation | Mostly application/domain output policy, using generic safe-writing primitives. Some generic test naming conventions may prove reusable later. |
| `prepare_image`, byte hashing, image payload creation, request-size checks | Largely reusable image/provider mechanisms. Accept ordered domain records; don't parse catalogue identifiers. Provider budgets/serialization need their own configuration. |
| Profile transport/generation settings, provider clients, key parsing, response normalization | Reusable execution/provider layer. Keep source-specific path discovery outside; accept resolved credentials/settings. Distinguish user test caps from provider entitlements. |
| `RateLimiter`, `DailyQuota`, transient/error classification, retries, reservation order, timeouts, client cleanup | Reusable core. Domain validation supplies a typed outcome/correction; core retains its retry/total-attempt/stop policies. No concurrency is currently present to extract. |
| Journal append/durability, atomic counters, locks, file collision handling | Reusable storage mechanisms with domain success/reuse normalization injected or handled above storage. Avoid moving the existing legacy note parser into a generic journal unchanged. |
| Generic run status, request attempts, model version, usage, completion vs retryable validation result | Candidate small common result types once usage sites are clear. Do not start with a large universal field schema. |
| Test execution, fake clocks/transports, reusable lifecycle assertions | Generic test support; specimen filenames, CSV fixtures, section rules, expected transcriptions remain domain tests. |
| Usage/cost accounting | Already extracted to `token_usage.py`. Preserve its domain-independent usage normalization, estimates, and aggregation; keep attempt reservation in the existing executor. |
| Concurrency, generic logging | Future opportunities, not implemented subsystems; print-based progress and sequential execution remain the current behavior. |

The tightest seams are between **record policy and execution**, and within validation between **provider completion** and **egg-slip grammar**. The prompt extraction improves visibility but leaves selection, validation, rendering, and orchestration coupling to address. Conversely, a universal filesystem/discovery module that understands `E` numbers, Family folders, or BACK OF SLIP would just relocate the same coupling under a misleading name.

## Generalization philosophy

**Extract the egg-specific assumptions now; generalize only as far as the current code naturally supports.** Here “now” means the next requested refactor after a reviewed Gemini baseline, not permission for unsolicited redesign or further paid model comparisons.

The engine should eventually know as little as possible about egg slips. A future collection should supply how files become physical records, what metadata is useful, how to ask for transcription, what response rules matter, and how to render/store its results. It should not need to rewrite provider clients, retry accounting, or safe writes.

Keep the existing egg-slip workflow fully functional throughout. Prefer extracting named functions/constants over designing an abstract base-class hierarchy. There is no current need for a marketplace, dynamic plugin loading, user-facing schema editor, arbitrary-domain CLI, GUI, workflow builder, or immediate second domain. A second real archival collection later provides evidence about which pieces genuinely deserve generalization.

## Future modularization strategy

This is a conservative proposal for a later, separately authorized change. The existing root CLI and import surface can remain the compatibility facade. A small `egg_slips.py` module or `egg_slips/` package plus the existing execution module may be enough initially; the handoff does not mandate a broad `core/providers/execution/retry/common` tree.

### Stage 0: capture the baseline

Use the established Flash-Lite profile and reviewed existing reports to choose a stable set/settings for regression work; no new provider comparison is required. Retain reviewed sample responses and request artifacts as described in [testing](testing.md#establishing-a-baseline-before-modularization). Run the full offline suite. Capture current CLI/default path behavior, side order, prompt bytes, result rendering, and normal cache hashes. Document intended changes separately from extraction.

### Stage 1: extract existing configuration and prompt policy

Prompt policy is already in `egg_slip_prompt.py`. Extract the remaining egg paths, catalogue column names, missing-card field/date rules, and filename patterns as needed without moving the prompt again merely to match a proposed layout. Keep execution profiles distinct from collection data configuration. Preserve exact prompt bytes and CLI defaults. Maintain the same public functions/imports temporarily where existing tests/users import `transcribe`.

Do not derive script/project paths from the new module's `__file__`: compute the entrypoint/data locations explicitly so `.env`, default quota state, and test-folder routing stay unchanged. The current top-level `MODEL` and `TEST_TEMPERATURE` edit workflow is user-facing behavior; preserve it or plan an explicit compatibility change rather than hiding settings in several new files.

### Stage 2: extract selection and physical-record grouping

Move `Database` and its CSV/routing helpers, `Card` creation, filename parsing, side mapping, grouping, sorting, and uncatalogued selection to the egg-slip layer. Let the orchestrator receive ordered record images and metadata rather than calculate E/CM labels. Initially retain the existing `Card` if changing it would make this step too broad; a generic record shape should emerge from actual call sites, not a guessed archival schema.

### Stage 3: extract domain validation and rendering

Split provider completion/answer extraction from egg section grammar and review policy. Keep `output_requirements`, format-correction content, `notes_have_content`, section recognition, CM/file banners, and output naming in the domain/application policy. Preserve legacy cached-note correction deliberately, preferably before/after generic journal lookup rather than inside storage. Keep available response text attached to validation failures.

### Stage 4: define the smallest necessary execution boundary

Based on those extracted functions, pass resolved generation/execution settings, ordered images/prompt, and validation/correction/render callbacks or small objects to the request lifecycle. A few ordinary functions/dataclasses may suffice. Provider adapters can later accept neutral text/image parts and return neutral answer/completion/usage data instead of emulating Gemini objects. Keep that provider-shape change separate if it threatens cache compatibility or broadens the diff.

The generic executor should need only whether a response is accepted, needs review, may be corrected, or must fail/stop—plus preserved answer text and correction instructions. It should not need to know what an egg catalogue number or `ANNOTATIONS:` means. Do not invent every status/interface ahead of the extraction or duplicate retry loops per domain/provider.

### Stage 5: prove equivalence after each stage

Run parsing/grouping, provider transport/retry/quota, cache, output, and test-mode regressions throughout, not only at the end. Replay the frozen responses and compare prompt/request/image ordering, cache keys, output bytes, and statuses. No change to the prompt or structural acceptance policy should slip in under “cleanup.” If a live check is specifically requested after deterministic equivalence is established, use the same representative Gemini samples and account for response variability. Fresh paid comparisons are not an extraction requirement.

The first refactor's objective is **make the current egg-slip implementation stop leaking egg-specific assumptions throughout the backend**, not build the perfect universal archival transcription platform.

## Repository hygiene and migration handling

The repository contains code, documentation, selected sample JPEGs, and previously tracked reference reports. The full production catalogue and collection remain local. Ignore rules exclude credentials, Python environments/caches, spreadsheet exports, the Family/data trees, most source-image formats, journals/locks, and default daily-counter files. Direct JPEGs under `tests/inputs/` are eligible for deliberate publication review.

New reports under `tests/outputs/` and the old `outputs/` location are ignored, but existing tracked reports are unaffected. The general `*_transcriptions_*.txt` ignore line is currently commented out, so do not claim that every generated report location is protected. Check actual Git status and staged content; custom report/counter paths may require exclusions. Do not change tracking or remove existing reference material during a documentation update.

The original uploaded legacy script contained a credential and was not imported as that legacy source. Historical notes do not establish whether the earlier key was revoked or audit unseen Git history. Never copy obsolete uploads, a local `.env`, source CSVs, SDK installations, or bulk generated results into a publication change.

The original Work handoff's hashes and inventory are historical. Current code/tests, local diffs, and the current overview above take precedence over the public tip or old archives. Preserve newer local and unpushed work.

The README's existing Apache License 2.0 declaration is retained. A standalone licence file is still absent; collection images and records retain separate rights. This documentation update does not select a new licence, grant collection-material rights, commit, or publish anything.

## How to continue development in Codex

1. Read `AGENTS.md`, this handoff, the README, and relevant focused docs.
2. Inspect current files, Git status/diff, and branch state. Local code may have advanced beyond this snapshot.
3. Install the documented dependencies in an isolated environment and run the offline tests. Record actual counts/skips and baseline failures before editing.
4. Inspect the existing curated samples and saved reference material; identify what has actually been reviewed before choosing baseline fixtures. Their presence is not authorization for live requests.
5. Trace the relevant code path and current domain/provider coupling, then implement the user's authorized scope with focused changes.
6. Preserve local work and source data; avoid combining prompt/quality changes with architectural extraction or changing the chosen provider without a request.
7. Run relevant regressions, then the full suite for cross-cutting work; compare the baseline artifacts when available.
8. Update current behavior docs and the architecture map when responsibilities or externally visible behavior change. Keep historical rationale labelled as history.

## Suggested next work

Continue production with Gemini 3.5 Flash-Lite and use the resulting collection review to curate a small, explicit reference set. Reuse existing saved responses for deterministic regression fixtures where appropriate. No paid GPT/OpenAI comparison is needed to proceed.

When the maintainer requests modularization, extract the remaining egg-slip selection/grouping, catalogue/missing-card policy, validation, and rendering responsibilities while preserving the existing prompt module, usage module, request/quota/journal lifecycle, and compatible fingerprints. Keep prompt tuning separate.

After that separation, consider concrete improvements such as uncertainty provenance or fuller replay manifests when requested. Leave second-domain experiments, concurrency, and framework features until real needs justify them.
