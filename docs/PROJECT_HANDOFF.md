# Project handoff: museum transcription

Prepared 22 September 2026 for moving development from ChatGPT Work to Codex. Application build: **2026-09-21.2**. This is technical institutional memory, not a specification for a framework that already exists.

## Purpose and context

The current program transcribes scanned historical museum egg-collection slips. The working collection has roughly 10,000 physical slips / 12,000 images, many form types, old scientific names, cursive and pencil, crossings-out, stamps, marginal additions, and occasional narrative backs. A physical slip can refer to several catalogue records; an image is not necessarily a whole record. A previously reported production CSV load contained 10,174 catalogue numbers across 10,190 data rows. Those are historical observations, not counts of data bundled here.

The maintainer works with these records and developed the initial program with Gemini, partly because ChatGPT was unavailable at work. Work revisions concentrated on input correctness, fidelity, resumability, explicit failure handling, and eventually repeatable model comparisons. The model reads the scan; the surrounding software protects ordering, selection, evidence, progress, and accountability. No public accuracy benchmark was established by the offline tests. User impressions of excellent accuracy should not become a measured performance claim.

The longer-term intent is a reusable system for other museum records, field notes, expedition documentation, handwritten forms, catalogue cards, and repeated archival series. Egg slips are the first and only implemented domain. The immediate objective is clean separation of existing responsibilities; immediate multi-domain support is not required.

## Authority and documentation map

**Current code + current tests = implementation truth. Conversation history = rationale and observed edge cases. Documentation = their durable bridge. Architectural intent = direction, not current functionality.** If these disagree, inspect the code, preserve working behavior, and update the relevant document explicitly.

| File | Role |
| --- | --- |
| [README.md](README.md) | Public overview, setup, commands, honest current scope. |
| [AGENTS.md](AGENTS.md) | Concise durable operational instructions for coding agents. |
| This handoff | Execution map, decisions, limitations, invariants, and future extraction plan. |
| [docs/filename_rules.md](docs/filename_rules.md) | Authoritative human explanation of current CSV, targets, paths, filenames, and grouping. |
| [docs/configuration.md](docs/configuration.md) | Current profiles, key loading, API adapters, pacing, quotas, and retries. |
| [docs/transcription_rules.md](docs/transcription_rules.md) | Current egg-slip SOP, validator boundaries, statuses, reports, and cache semantics. |
| [docs/testing.md](docs/testing.md) | Offline verification, real-image fixture, live comparisons, and baseline strategy. |
| [transcribe_notes.md](transcribe_notes.md) | Preserved revision history; older instructions are superseded where noted. |

Do not duplicate an entire rule table across documents. Update its focused document and link it from overview/handoff material. Prompt changes must update the actual executable prompt, not just prose documentation.

## Current state and verification

The authoritative implementation for this pass was the current Work `transcribe.py` and `test_transcribe.py`, not the public GitHub version. Their SHA-256 values are recorded to make this snapshot unambiguous:

```text
transcribe.py       85b1e15887b6ee9ab7eacec15a783443012690a07f466a0d365f4743766bcea3
test_transcribe.py  4d31171e7ad85add4f6552f953499762216648d01ca223f11ef640be3ae2a7f6
```

The public checkout used only as the repository/layout baseline was commit `48874132da9696189a22bdcfad1c66f3b4d85b06` (`main`, 20 September 2026). It contained `.gitignore`, the script, tests, and revision notes; all three Work files were newer/different. They were overlaid onto the checkout before documentation work. Consequently a Git diff against that commit includes **pre-existing application/test changes**. Those are not new functionality authored by this handoff task. No commit or push was made, and the maintainer's actual Windows checkout/unpushed diff was not available for direct inspection.

Working capabilities include normal species/exact-number/CSV-row selection, both supported folder layouts, shared slips, ordered multiple sides, front-only inputs, explicit uncatalogued groups, conservative prompt rules, output/status validation, durable journals, model profiles, persistent daily counters, bounded service/format retries, an optional OpenAI adapter, and independent mixed-species model/temperature tests.

Baseline and final post-documentation verification each ran **115 offline tests, all passing with zero skips**, using both installed SDKs and the original three-image fixture. A separate fresh-checkout-style run without the optional image directory discovered 115 tests: **114 passed, one expected sample-fixture skip**. Documentation links/anchors, CLI option names, ignore rules, whitespace, and credential-pattern checks passed. The application and test-file hashes above remained unchanged. The environment and exact commands/skip conditions are in [testing](docs/testing.md). No live requests were made. The application version remains unchanged because this pass does not change its behavior.

Newly prepared documentation/configuration includes the README, this handoff, concise agent instructions, four focused docs, direct dependency pins, a blank credential example, ignore rules, and input/output folder READMEs. The previous revision notes are retained verbatim below a supersession notice. No source photographs, catalogue export, credentials, generated results, or quota state were added.

The maintainer will add a hand-selected 10–15-card sample set before Codex takes over. Earlier individual attachments were available in Work, but they were not automatically promoted into that set. A full production catalogue, reviewed golden transcriptions, quantitative model comparisons, Windows/Drive integration results, and account-specific live access evidence are not part of this repository snapshot. Missing samples are expected, not a reason to fabricate them or block documentation.

## Likely development sequence

1. Finish Gemini model/temperature comparisons using the test target.
2. Begin OpenAI vision/model comparisons using the implemented adapter and verified account settings.
3. Establish a reviewed representative egg-slip baseline, including deterministic request/response fixtures.
4. Extract egg-specific configuration, prompts, discovery/parsing/grouping, validation, and output from reusable execution machinery.
5. Confirm the offline suite and sample baseline retain current behavior; distinguish nondeterministic model changes from code changes.
6. Continue targeted egg-slip improvements on the separated architecture.
7. Much later, try a second real historical-document collection to test whether the boundary is useful.

This is a roadmap, not permission for an agent to start every step or launch live comparisons on its own. The first Codex orientation should inspect and report without editing. Model testing precedes a major refactor so there is a stable, understandable baseline; do not tune prompts, change models, and reorganize execution in one unreviewable change.

## Architecture: current execution flow

There is one application module, `transcribe.py`, and one standard-library `unittest` module, `test_transcribe.py`. There is no package/domain registry, database server, UI, background worker, or concurrency pool. Numbered source comments identify nine broad sections. Imports do not call APIs; SDK/image imports are mostly delayed until needed.

| Phase and actual symbols | Current behavior | Boundary observation |
| --- | --- | --- |
| `main`, `parse_args`, `ModelProfile` | Resolve CLI/profile defaults; print build, script, interpreter, selected limits. `--version`, `--help`, `--list-models`, and `--check-config` have early paths. | CLI combines execution settings with museum paths and test orchestration. |
| `run`, `load_database`, `Database` | Load CSV before the target prompt; index E-numbers, row numbers, species/family mappings, retaining duplicate rows. | Strong egg-slip assumptions; even test mode requires a CSV. |
| `select_targets`, `enum_species`, `species_name` | Resolve species, exact E-number, console-star, or inclusive row selection. `test` is recognized separately in `run`. | Domain selection and generic run mode are intertwined. |
| `resolve_folders`, `child_directory` | Find exactly one JPEG directory using CSV family/species mapping and either supported layout. | Source organization policy, not engine policy. |
| `discover_cards`, `side_number`, `Card` | Parse JPEG names; group physical slips; order/label sides; collect file warnings; append uncatalogued groups. Test mode adds unmatched-CSV warnings. | `Card.enums` and literal FRONT/BACK labels make the record object domain-specific. |
| `build_prompt`, `output_requirements`, `BASE_PROMPT` | Assemble the SOP, actual side requirements, warnings, shared-record references, and optional separate CSV hints. | Domain policy. It knows exactly what counts as a valid egg-slip response. |
| `prepare_image`, `prepare_card` | Decode JPEGs; preserve bytes if possible; apply EXIF orientation/optional resize in memory; calculate payload estimate and a SHA-256 fingerprint; construct ordered labelled request parts. | Image handling is reusable; labels/manifests and Gemini-shaped parts mix other concerns. |
| `species_lock`, `Journal`, `open_output_report` | In normal saved mode, acquire a species lock, open journal and new report before spending requests. Test mode opens a report but never a journal. | Generic safety primitives have domain naming/storage and success policy embedded. |
| `Journal.reusable` | Accept latest matching `ok`/`review` entry; correct the historical empty-notes warning locally. | Storage code knows domain statuses and section headings. |
| `Transcriber.ensure_client` | Lazy provider import, key lookup, explicit endpoint, timeout, SDK retry disabling. No credential is requested for all-cache reuse. | Mostly reusable; key search still depends on CSV/Family settings and `__file__`. |
| `RateLimiter`, `DailyQuota`, `Transcriber.transcribe` | Pace, reserve quota, issue request, normalize OpenAI, validate, correct format once, retry service errors within budget, classify failures/stops. | Core execution directly invokes egg-specific validation and retry instructions. |
| `validate_response`, `section_headers`, `notes_have_content` | Exclude thought text, check completion/sections/plain-text constraints, derive warnings and token usage. | Provider completion validation and egg-slip grammar share one function. |
| `Journal.append`, `durable_write`, `output_block` | Save a new result durably before readable report text; render CM/file banners/status/reviews; preserve failed answer text. | Journal durability is reusable; rendering/status interpretation is largely domain policy. |
| `run` cleanup/exit | Close client, retain completed writes, print totals, stop on fatal errors/quota, return nonzero on failures/discovery issues. | Job lifecycle remains mixed with species report aggregation and test footers. |

`--dry-run` performs CSV/routing/group discovery and lists sides, without image decoding, API/key lookup, journals, reports, quota files, or folder creation. It can reveal names/order issues but does not establish scan integrity or credentials.

Console-only normal runs make fresh API calls with no report or transcription journal. They still write the persistent quota state/lock. This supersedes early chat/notes statements that console mode writes no files at all.

Test mode routes every recognized card in one flat directory through the same parsing/prompt/image/provider/validation machinery. It skips production folder lookup, marks missing CSV references for review, uses `TEST_TEMPERATURE` unless explicitly overridden, and writes one model-tagged report. It never opens a `Journal`, even if production cache entries would match. A restart after a partial test starts at the first card again.

Exit code 0 means no recorded failed/paused/discovery issues; accepted review results do not make the run fail. Code 1 covers run failures, missing/ambiguous files/routing, quota pauses, or an empty test set. Keyboard interruption returns 130. Argument-parser errors use argparse's code 2. A fatal stop can happen before the final totals/footer, so read the actual messages and report termination state.

## Configuration and model system

The exact profile table, parameter precedence, lookup paths, and retry rules are maintained in [configuration](docs/configuration.md). Important orientation points:

- Current default: `gemini-3.5-flash-lite`, normal temperature 0.1, 15 RPM / 500 local daily attempts. Configured `gemini-3.6-flash` and `gemini-3.8-flash` use 5 RPM / 20 daily attempts. These were the maintainer's allowances, not general provider guarantees.
- Optional OpenAI `gpt-5.6-luna` profile: implemented Responses adapter, 5 RPM / 20 local test cap, normal temperature omitted. Its existence in a dictionary is not proof of current account access.
- `MODEL` chooses the entire profile. Unknown IDs fail locally. A model switch should not accidentally retain the previous model's timing or generation options.
- Test temperature is a separate code setting immediately below model selection; an explicit CLI temperature wins. **OpenAI tests need `--temperature auto` if they should omit temperature**, because `TEST_TEMPERATURE` otherwise overrides that profile default.
- Gemini and OpenAI receive the same evidence/instructions, with provider-specific serialization and generation options. Both clients disable their hidden automatic retries so the script controls and accounts for every call.
- Daily state persists beside the script by default and is shared across normal/test/console runs and restarts. It is keyed by provider/model, not key/project. It is not a server quota meter or distributed scheduler.
- A 503 means service unavailable; it does not prove the daily cap was reached. The reported “one card then 503” motivated better configuration and bounded waits, not a fabricated diagnosis.
- One invalid-response correction is allowed within the total per-card request budget. Service failures may consume other attempts. Token cutoffs are retained as failures; they do not trigger an endless retry with the same cap.
- Keys come from a local `.env` search before process variables, using a built-in key-only reader. Automatic hidden prompting was removed; `--prompt-key` makes manual entry explicit. `.env` lookup success is not authentication success.

The code has a dated Gemini 401 migration hint inherited from troubleshooting. It should be treated as historical provider guidance and checked against current official documentation if that error returns. The exact cause of the maintainer's earlier rejected credential was not established. Do not promise that an `.env` change repairs an API-rejected key.

The source still uses the maintainer's Windows CSV/Family defaults. Moving `transcribe.py` changes its default `.env` and quota-file location: deliberately retain or point `--quota-file` to the existing state. Do not use a new counter to pretend earlier requests never happened. No live credentials or source catalogue were needed for this documentation pass.

## Input and filesystem conventions

[Filename rules](docs/filename_rules.md) owns the complete grammar and selection table. The essentials to retain during extraction are:

- Real scans live under a CSV-derived family/species directory, optionally with a genus directory, then `JPEG`. Only direct JPG/JPEG files are read. Folder matching is case-insensitive and rejects ambiguity.
- The master file is a CSV export with exact `catalogNumber`, `Scientific Name`, and `Family` headers, not arbitrary project spreadsheet columns or `.xlsx` parsing. Other museum graphing/indexing tools discussed elsewhere are not part of this repository.
- `_E<digits>` tokens identify records; every number in a shared filename can select the group. Leading zeros remain meaningful. Multiple E-numbers do not mean multiple copies of the same physical scan/request.
- A/B or numeric side suffixes identify ordered images; unlettered/A is front. Lone fronts are normal; missing fronts/gaps are warnings; duplicate sides are errors.
- `_exchanged` is accepted after the optional side suffix and excluded from group identity, while original filenames remain in output. Other arbitrary suffixes are not quietly accepted.
- Explicit `Uncatalogued`/`Uncataloged` patterns permit scans absent from the sheet. Species and visited row-range folders include them; exact E-number targets do not. They appear after numbered groups.
- `E123*` means one fresh console-only E-number reading, **not a wildcard**. `2-1000` means CSV row numbers, **not an E-number range**.
- Test paths default to `tests/inputs` and `tests/outputs` beside the configured Family directory. They are not inherently repository-relative. Explicit overrides make the checkout's prepared folders usable.

All of these selection/record/folder rules are domain behavior. Safe path checks, image decoding, in-memory transforms, file locks, and durable writes are potential reusable mechanisms. Even image discovery has two parts: generic filesystem enumeration and domain-specific admissible paths/names/grouping. Avoid placing the latter in a supposedly generic loader.

## Prompt and transcription architecture

`BASE_PROMPT` is a substantial literal string in source section 2. `build_prompt` appends `output_requirements(card)`, file warnings, multi-number references, and JSON catalogue hints for each matched record. Missing and uncatalogued records receive no invented reference values. `--no-csv-hints` is an ablation option, not a no-CSV execution mode.

`prepare_card` places a filename and explicit section label immediately before each image. The model is told how many front/back images were actually supplied and which back headings are expected, so a generic template cannot require a nonexistent back. The format retry adds a correction to the original evidence; it does not use the faulty answer as source truth or mutate the original request contents.

The detailed SOP is in [transcription rules](docs/transcription_rules.md): visible collection headings first; dynamic `Label: value`; separate stamps/fields; original spelling/units; carefully scoped ditto expansion; readable brace-group dimensions; plain fractions; uncertain/inferred readings in brackets; meaningful annotations; one final notes section; all supplied sides. These are primarily domain rules, not universal archival grammar.

The hand-written Hanna sample supplied a formatting model, not permission to modernize or normalize every word. The user later corrected a collector reading on a difficult Brandt slip to H. W. Brandt. The prompt permits that candidate only when visible strokes and context support it, rather than unconditionally substituting collection ownership for collector identity.

The backend should eventually receive an already-built domain prompt and validation/correction policy. A second collection should be able to replace these without modifying API execution. Initially move the existing prompt **byte for byte**: even a whitespace change changes its fingerprint and may spend quota retranscribing every selected normal card.

## Output architecture and review philosophy

[Transcription rules](docs/transcription_rules.md#reports-and-ordering) owns the exact report, banner, section, spacing, and cache conventions. In brief, normal runs write one report per visited species in its family folder, with matching successful journal reuse. Test runs write one independent mixed-species report with model/temperature suffixes and no journal. Both use minute timestamps with collision counters, UTF-8, durable incremental writes, and retained failed answer text.

`output_block` knows CM labels, catalogue-number lists, filename banners for uncatalogued material, model/source metadata, review lines, and two blank lines. This is egg-slip rendering. `open_output_report` and `durable_write` contain reusable file safety, but the calling code supplies domain naming/location/aggregation. Another domain should eventually choose its own renderer and storage plan without reimplementing fsync/collision handling.

`OK` is structurally accepted, not human-verified. `REVIEW` is accepted with warnings and is reusable normally. `FAILED` and `PAUSED` are not completed cache results. “Annotations” are artifact content; “transcription notes” explain reading/physical problems. Empty/None notes do not imply a problem. The current bracket heuristic still misclassifies some literal printed brackets as uncertainty.

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
| Printed bracketed form code looks like model uncertainty. | Regex flags it for review. | Confirmed false-positive class; no source-safe provenance distinction yet. Domain policy. |
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

**Keep the working default until measured comparisons exist.** Flash-Lite's request allowance made large batches practical. Temperature 0.1 was retained to separate workflow repairs from quality tuning; 1.0 was discussed as a comparison candidate. No evidence in this project establishes one temperature/model as universally superior, nor a cost winner. Do not convert past provider recommendations into benchmark results.

**Preserve original image detail and journal exact inputs.** Automatic 2,000-pixel shrinking was removed as the default so optional resolution loss is explicit. Orientation/resize changes operate on copies in memory. Fingerprints include what was actually sent, avoiding stale reuse after a scan or prompt changes. The original Gemini manifest shape was deliberately preserved when provider profiles were added.

**Bypass caches for comparisons, retain them for production.** Reusing a prior answer invalidates a model/temperature experiment. Test mode always rerequests, including after interruption. Normal mode avoids paying again for matching completed work. Changing only rate settings should not invalidate that work.

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
| **Confirmed false-positive behavior** | Literal bracketed print is counted as uncertain, except `[blank]`. It can cause REVIEW without an actual uncertain reading. No text-safe disambiguation fix has been implemented. |
| **Known limitation** | Structural validation cannot detect every omission, incorrect word, false blank back, invented field, or misassigned dimension. The plain-text prompt is stronger than the implemented Markdown checks. |
| **Known limitation** | No human-reviewed gold set, repeatable accuracy metric, full test-run manifest, cost estimator, or automatic model ranking. Success token usage is stored in normal journals, not comprehensive failed-attempt/cost accounting. |
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
| **Verification gap** | Windows locking/Drive sync, full production catalogue, live SDK/API/model compatibility, provider quotas, and live handwriting/signature improvements were not verified here. Mocked request serialization is useful but narrower evidence. |
| **Test infrastructure tradeoff** | Optional SDK/scan tests skip when unavailable; the original-image test expects exactly three specific matching JPEGs. Curated live samples are not yet a deterministic baseline. Several tests import a monolithic `transcribe` facade, constraining first extraction. |
| **Public-repository decision pending** | No licence selected, no sample publication provenance established, original exposed-key rotation not verifiable. Bulk dataset should remain local; review actual staged content before pushing. |
| **Future ideas, not requirements** | A second document domain, better uncertainty provenance, a full run manifest, token/cost reporting, reviewed response fixtures, and eventual concurrency can be considered after the comparison/baseline/extraction sequence. |

Do not fold these into this documentation task as surprise functional changes. If a later task addresses a bug, distinguish the intentional behavior change from a behavior-preserving extraction.

## Architectural direction: reusable backend versus domain layer

**Current:** a single egg-slip module with two provider paths and reusable mechanisms embedded in it. **Intended:** a small collection layer supplies record discovery/grouping, metadata, prompt, validation, and rendering; execution infrastructure handles requests and safe result lifecycle. Neither a generic domain interface nor a `core/` package exists yet.

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
| Usage/cost accounting, concurrency, generic logging | Future opportunities, not complete existing subsystems. Present token fields/print calls are the actual starting point. |

The tightest seams are between **record policy and execution**, and within validation between **provider completion** and **egg-slip grammar**. Moving only a prompt string would help visibility but would leave most coupling intact. Conversely, a universal filesystem/discovery module that understands `E` numbers, Family folders, or BACK OF SLIP would just relocate the same coupling under a misleading name.

## Generalization philosophy

**Extract the egg-specific assumptions now; generalize only as far as the current code naturally supports.** Here “now” means the first refactor after model comparisons and a baseline, not a request to redesign during this handoff.

The engine should eventually know as little as possible about egg slips. A future collection should supply how files become physical records, what metadata is useful, how to ask for transcription, what response rules matter, and how to render/store its results. It should not need to rewrite provider clients, retry accounting, or safe writes.

Keep the existing egg-slip workflow fully functional throughout. Prefer extracting named functions/constants over designing an abstract base-class hierarchy. There is no current need for a marketplace, dynamic plugin loading, user-facing schema editor, arbitrary-domain CLI, GUI, workflow builder, or immediate second domain. A second real archival collection later provides evidence about which pieces genuinely deserve generalization.

## Future modularization strategy

This is a conservative proposal for a later, separately authorized change. The existing root CLI and import surface can remain the compatibility facade. A small `egg_slips.py` module or `egg_slips/` package plus the existing execution module may be enough initially; the handoff does not mandate a broad `core/providers/execution/retry/common` tree.

### Stage 0: capture the baseline

Finish the model comparisons and choose a stable set/settings for regression work. Retain reviewed sample responses and request artifacts as described in [testing](docs/testing.md#establishing-a-baseline-before-modularization). Run the full offline suite. Capture current CLI/default path behavior, side order, prompt bytes, result rendering, and normal cache hashes. Document intended changes separately from extraction.

### Stage 1: extract existing configuration and prompt policy

Move egg paths, catalogue column names, filename patterns, prompt literal, and prompt assembly helpers together. Keep execution profiles distinct from collection data configuration. Preserve exact prompt bytes and CLI defaults. Maintain the same public functions/imports temporarily where existing tests/users import `transcribe`.

Do not derive script/project paths from the new module's `__file__`: compute the entrypoint/data locations explicitly so `.env`, default quota state, and test-folder routing stay unchanged. The current top-level `MODEL` and `TEST_TEMPERATURE` edit workflow is user-facing behavior; preserve it or plan an explicit compatibility change rather than hiding settings in several new files.

### Stage 2: extract selection and physical-record grouping

Move `Database` and its CSV/routing helpers, `Card` creation, filename parsing, side mapping, grouping, sorting, and uncatalogued selection to the egg-slip layer. Let the orchestrator receive ordered record images and metadata rather than calculate E/CM labels. Initially retain the existing `Card` if changing it would make this step too broad; a generic record shape should emerge from actual call sites, not a guessed archival schema.

### Stage 3: extract domain validation and rendering

Split provider completion/answer extraction from egg section grammar and review policy. Keep `output_requirements`, format-correction content, `notes_have_content`, section recognition, CM/file banners, and output naming in the domain/application policy. Preserve legacy cached-note correction deliberately, preferably before/after generic journal lookup rather than inside storage. Keep available response text attached to validation failures.

### Stage 4: define the smallest necessary execution boundary

Based on those extracted functions, pass resolved generation/execution settings, ordered images/prompt, and validation/correction/render callbacks or small objects to the request lifecycle. A few ordinary functions/dataclasses may suffice. Provider adapters can later accept neutral text/image parts and return neutral answer/completion/usage data instead of emulating Gemini objects. Keep that provider-shape change separate if it threatens cache compatibility or broadens the diff.

The generic executor should need only whether a response is accepted, needs review, may be corrected, or must fail/stop—plus preserved answer text and correction instructions. It should not need to know what an egg catalogue number or `ANNOTATIONS:` means. Do not invent every status/interface ahead of the extraction or duplicate retry loops per domain/provider.

### Stage 5: prove equivalence after each stage

Run parsing/grouping, provider transport/retry/quota, cache, output, and test-mode regressions throughout, not only at the end. Replay the frozen responses and compare prompt/request/image ordering, cache keys, output bytes, and statuses. No change to the prompt or structural acceptance policy should slip in under “cleanup.” Use the same representative image set for authorized live comparisons once deterministic equivalence is established, with model variability explicitly accounted for.

The first refactor's objective is **make the current egg-slip implementation stop leaking egg-specific assumptions throughout the backend**, not build the perfect universal archival transcription platform.

## Repository hygiene and migration handling

The repository contains code and documentation, not the production collection. Ignore rules exclude `.env` variants except `.env.example`, virtual environments/caches, the Family/data directories, spreadsheet exports, source image formats by default, generated reports/journals/locks, and default daily-counter files. Direct JPG/JPEGs in `tests/inputs/` are deliberately eligible for reviewed samples. `tests/outputs/` remains ignored except its README. Custom counter/report paths need their own ignore entries.

The original uploaded legacy script contained a credential and was not imported into the repository. The revised Work source contains no real key. That does not establish whether the earlier key was revoked, or audit an unseen local/remote Git history. Check staged changes and rotation status before publishing; do not copy obsolete uploads, entire Work scratch directories, SDK installations, source CSVs, or generated reports into Git.

Only the available Work implementation and fetched public tip were inspected. Any additional Windows-local edits remain outside this view. Apply the documentation files to the actual local checkout, preserving newer code, and rerun its tests. Do not overwrite newer unpushed code with the public tip or an old archive merely to reproduce these handoff hashes. Documentation should be updated if that actual checkout has additional behavior.

The handoff did not choose a software licence or assert rights over museum sample images. Those remain maintainer decisions. It prepared the folders but did not add thousands of scans, invent sample images, delete/relocate data, commit, or push.

## How to continue development in Codex

1. Read `AGENTS.md`, this handoff, the README, and relevant focused docs.
2. Inspect current files, Git status/diff, and branch state. Local code may have advanced beyond this snapshot.
3. Install the documented dependencies in an isolated environment and run the offline tests. Record actual counts/skips and baseline failures before editing.
4. Check whether the intended curated samples and reviewed baselines have now been added. Do not equate their presence with authorization to call a paid API.
5. Trace the relevant code path and current domain/provider coupling. Report understanding and a narrow proposed boundary in the first orientation session without modifications.
6. On a subsequent authorized task, make focused changes, preserve local work and source data, and avoid combining prompt/quality changes with architectural extraction.
7. Run relevant regressions, then the full suite for cross-cutting work; compare the baseline artifacts when available.
8. Update current behavior docs and the architecture map when responsibilities or externally visible behavior change. Keep historical rationale labelled as history.

## Suggested next work

The next practical work is finishing the handpicked samples and Gemini temperature/model comparisons, then testing OpenAI with explicit compatible settings. Turn those observations into a reviewed baseline before extracting domain policy. The first extraction should center on existing egg-slip selection/grouping/prompt/validation/rendering responsibilities while keeping the proven request/quota/journal lifecycle stable.

After that separation, consider concrete egg-slip improvements such as uncertainty provenance and more informative comparison manifests if the maintainer requests them. Leave second-domain experiments, concurrency, and richer framework features until real needs justify them.
