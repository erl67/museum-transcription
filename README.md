# Museum Transcription

Turn scanned egg-collection slips into readable, searchable text while keeping each transcription connected to its source. Museum Transcription brings together the front, back, and additional sides of a physical card, relates them to catalogue references, and produces plain-text reports for collection staff to check against the original images.

The project grew from a natural-history collection of roughly 10,000 slips and 12,000 images: handwritten and typed forms, historical scientific names, pencil additions, stamps, corrections, and narrative notes. Its purpose is to make that documentation easier to consult and review while preserving the wording and uncertainty that give the records their value.

The current application is a Python command-line tool for egg slips. It creates UTF-8 text reports; it does not update the collection catalogue or alter source scans. Support for other archival document collections remains a future development direction.

## Designed around collection records

- **Keep the physical record together.** All supplied sides travel through one transcription request in order. Shared slips retain every catalogue reference, and front-only cards are valid records.
- **Preserve the source.** Reading instructions retain historical names, spelling, abbreviations, units, symbols, partial dates, and meaningful alterations. Catalogue values assist a reading but do not replace visible text.
- **Accommodate different forms.** Reports follow the fields on each card, including multiline entries, margins, stamps, and narrative backs, rather than imposing one field template on the collection.
- **Make uncertainty visible.** Bracketed readings and concise transcription notes identify passages for review. Annotations record content on the artifact; transcription notes explain reading issues.
- **Include gaps in the catalogue-to-scan relationship.** Explicitly named uncatalogued slips appear at the end of applicable reports. Selected catalogue records without a matching JPEG receive clearly marked, catalogue-derived `(MISSING)` blocks.
- **Retain a record of processing.** Source filenames, catalogue banners, settings, version information, and request fingerprints accompany new transcriptions. Completed normal results are checkpointed before the readable report is written.

The established processing choice is **Gemini 3.5 Flash-Lite** (`gemini-3.5-flash-lite`). The maintainer is satisfied with its readings for the current collection and intends to continue using it for production. Selected images and enabled catalogue hints are sent to the configured Gemini service; file selection, grouping, validation, progress tracking, and report writing happen locally. This is not an offline transcription tool.

## Getting started

Use **Python 3.10 or later**, a compatible CSV export, JPEG scans, and a Gemini API key. The working installation uses Windows and a mounted Google Drive folder; both data paths can be changed. Excel is not required.

From the repository root, create an environment and install the Gemini dependencies. These versions match the repository's recorded dependency pins:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install google-genai==2.23.0 Pillow==12.3.0 tzdata==2026.3
```

On macOS/Linux, activate the environment with `source .venv/bin/activate`. The complete development dependency list is in [docs/requirements.txt](docs/requirements.txt).

Create a plain-text file named `.env` **beside `transcribe.py`**, containing `GEMINI_API_KEY=` followed by your own key. Keep it local and out of Git. On Windows, check that the filename is not `.env.txt`. The application reads this file itself; no additional environment-file package is needed.

```text
python transcribe.py --check-config
python transcribe.py --help
```

`--check-config` checks local credential lookup without contacting the service or reading collection data. It does not confirm that the service will accept the key. See [configuration](docs/configuration.md) for lookup precedence and troubleshooting.

## Prepare the catalogue and scans

The catalogue must be a UTF-8 CSV export with the exact headers `catalogNumber`, `Scientific Name`, and `Family`. Optional collector and locality columns provide reading hints. A workbook with an `.xlsx` extension cannot be read directly.

By default, the application reads `G:\My Drive\Egg Slip Scanning\EggSlipReorganizationProject_FULL.xlsx - Full List.csv`, the same CSV used by the installed automated campaign, and scans under `G:\My Drive\Egg Slip Scanning\Family`.

After changing the master workbook, export its **Full List** sheet to that Drive CSV and let Drive finish syncing. No repository-folder CSV copy is needed. If the selected CSV is unavailable, the program stops rather than falling back to another copy. The supported layouts are:

```text
Family/<family>/<Genus_species>/JPEG/<scan>.jpg
Family/<family>/<Genus>/<Genus_species>/JPEG/<scan>.jpg
```

`--base-dir` points to the **Family root**, not a species folder. Use `--csv` and `--base-dir` to select other locations:

```powershell
python transcribe.py Accipiter_cooperii --csv "C:\Collection\catalogue.csv" --base-dir "C:\Collection\Family" --dry-run
```

Filenames identify catalogue numbers and sides: for example, `Accipiter_cooperii_E4268(A).jpg` and `Accipiter_cooperii_E4268(B).jpg`. Complete E-numbers are matched, including numbers on shared slips; leading zeros are significant. Ambiguous sides or directories are reported for correction. Full conventions are in [input and filename rules](docs/filename_rules.md).

## A typical working session

1. **Preview the selection.** Run a species or row range with `--dry-run` to check card grouping, side order, and missing scans. A dry run makes no service requests or output files; it does not decode images or test their readability.
2. **Create the report.** Repeat the command without `--dry-run`. Keep one live batch running at a time so request pacing and the local daily allowance remain useful.
3. **Review against the scans.** Check flagged passages, dates, quantities, names, and front/back continuations. Retain the source image as the authority for the reading.
4. **Keep the report and progress journal.** If processing stops, rerun the same target. Matching completed results saved within the last 48 hours can be reused; older results remain on disk but require fresh requests when selected again.

Run `python transcribe.py` for an interactive target prompt, or supply a target directly. The following identifiers illustrate syntax; the matching source records must exist in your data.

| Command | Result |
| --- | --- |
| `python transcribe.py Accipiter_cooperii --dry-run` | Preview a species and its ordered card groups. |
| `python transcribe.py Accipiter_cooperii` | Save a species report, including uncatalogued cards and selected catalogue records without scans. |
| `python transcribe.py E4268` | Process one exact catalogue number, retaining all sides and shared references. |
| `python transcribe.py "2-1000"` | Process inclusive CSV row numbers; row 1 is the header. Includes uncatalogued cards in visited species folders. |
| `python transcribe.py "E4268*"` | Make a fresh reading and print it in the terminal. The star is a mode suffix, not a wildcard. |
| `python transcribe.py "E9323!"` | Make a fresh reading, print it, and save an individual report with the selected model's tag. |
| `python transcribe.py E4268 --force` | Request a fresh reading even if a reusable result exists. |

The `*` and `!` modes bypass transcription caches; request accounting still applies. The additional `@` shortcut selects a different Gemini profile and is documented under [single-card checks](docs/testing.md#single-card-fresh-checks). It is not needed for the default workflow.

## Reports and collection review

Normal reports and per-species progress journals are saved in the **family directory**, above the species folders. A row range visiting several species produces separate species reports. Examples:

```text
Accipiter_cooperii_transcriptions_YYYYMMDD_HHMM.txt
Accipiter_cooperii_transcriptions_cache.jsonl
E9323_g35fl_Hylopezus_perspicillatus_YYYYMMDD_HHMM.txt
```

Repeated report names receive a counter rather than overwriting an earlier file. Each transcribed physical card has aligned CM banners, source filenames, processing metadata, its reading, and two blank lines before the next record. Uncatalogued material uses filename banners. Available failed response text is kept for inspection.

| Report marker | How to interpret it |
| --- | --- |
| `OK` | The response passed structural checks without warnings. This is not a record of human verification. |
| `REVIEW` | The reading was accepted with flags, such as bracketed passages or side warnings. Transcription notes alone do not trigger this status. |
| `FAILED` | An input, request, or response check failed. Inspect the error and any retained text. |
| `PAUSED` | A quota or service condition stopped processing. Completed saved work remains available. |
| `(MISSING)` | No matching JPEG was found for a selected catalogue number in its resolved species folder. The block contains selected CSV values, not a transcription of an unseen card. |

Missing-card blocks preserve partial dates, omit empty selected fields, and refresh from the CSV each run without spending request quota. A missing or ambiguous species directory remains an error; it does not establish that the physical cards are absent from the collection.

The reading rules cover set marks in fields and margins, including short codes and fractions. Plausible unlabelled marks are annotated as “Likely set mark …”; no mark is supplied when absent. Statements that a nest, skin or bird specimen was collected are highlighted in annotations with any associated reference numbers, preserving uncertainty and negation.

Foreign-language text, including Icelandic and German, is retained with an English translation in parentheses and a disclosure in transcription notes. An English account on the back can help interpret the front, while each side retains its own wording and details. Collector-specific guidance for Brandt handwriting and Steinbach German notes remains. Notes are normal report content and do not by themselves require review. Harmless layout differences and recognized printed form codes do not by themselves require review. A lack of flags cannot establish that every word or line was read correctly. See the [transcription and output rules](docs/transcription_rules.md) for the complete policy.

[Egg Slip Record Search](apps_script/transcription_viewer/README.md) retrieves a record from the latest matching species report when its link is opened. Share its plain deployment URL ending in `/exec` to let readers enter an E-number and choose **Find record**, or link directly from the spreadsheet. The empty search box shows **E4268** as an example. The browser tab is titled **Egg Slip Record Search** before a search and, after a successful lookup, **E4268 Egg Slip Record** (using the requested number). The page heading, **Egg-slip transcription / scan viewer**, describes access to both readings and source images. The viewer uses the catalogue CSV export in Drive for E-number lookup; links supplying family/species skip that lookup. The master workbook still controls access, and the CSV and Family data need matching reader permissions. Refresh the CSV when catalogue entries change. Record text appears first, then scans load below it, centered and labelled by side. When no transcription exists, the viewer can show current scans found by the complete E-number. Catalogue-only records stay clearly identified. The viewer reads existing Drive files without making transcription requests, keeps transcription text out of the spreadsheet, and excludes individual `!`/`@` reports. Python continues to use its configured CSV unchanged.

[Open Egg Slip Record Search](https://script.google.com/macros/s/AKfycbzisn0ISa_2hwEh_vIaQporGeXxruTwscyAOalTgubqPV9EXvkleFlXyKx8aTezEa6EyA/exec?) to search directly by E-number.

## Processing settings and continuity

The default profile uses temperature **1.0**, thinking level **high**, original image resolution, **15 requests per minute**, and a local cap of **500 attempts per day**. These are configured project settings, not guarantees of account entitlement or daily throughput. Retries count toward the cap. The application never switches services automatically after a failure.

Normal reuse requires matching images, ordered filenames, reading instructions, relevant hints, and generation settings, as well as a completed result no more than 48 hours old. Changing those inputs can trigger fresh requests. `--force`, console checks, individual fresh reports, and the `tests` target also make new requests. Retaining reports alone does not make them reusable progress records.

Keep `transcribe_request_usage.json` beside the script when moving or updating the installation, or continue using the same `--quota-file` path. It preserves local request counts across restarts. Report footers show fresh call counts, token usage, and estimated standard paid-rate costs; estimates are not invoices and do not establish whether an account is being charged. [Configuration and request control](docs/configuration.md) explains the limits, retries, and accounting.

## Verification and continued development

For a reviewed, unattended multi-day run, see [campaign setup and recovery](docs/campaign.md).
Discovery and transcription proceed alphabetically by family, then species within
each family, and continue from the remaining eligible cards on subsequent days.
The separate `campaign.py` worker retains completed cards beyond 48 hours, uses the existing
daily attempt accounting, and provides offline status, pause/resume and recovery commands.
Routine campaign scans check names and file metadata without reading image contents;
they display progress. Images are read when selected for processing, with a separate
`verify` command available for a deliberate full content check.
Keep its transactional state on the designated home desktop's local disk. Scheduling support
prepares a disabled Windows task; enabling production processing is a separate deployment step.

The sample folder currently contains **11 physical cards / 19 JPEGs**, including fronts, pairs, a shared slip, and a three-sided card. Preview it with:

```text
python transcribe.py tests --dry-run
```

Running `python transcribe.py tests` makes fresh Gemini requests and saves one combined report in `tests/outputs/`; it never reads or writes transcription caches and starts from the first card each time. Ordinary code verification uses the offline suite:

```text
python -m unittest -v test_transcribe.py
```

For build **2026-10-14.1**, verification on 14 October 2026 ran **169 tests: 168 passed and one optional original-image fixture was skipped**. Service transports were simulated; no live requests were made for this review-policy change. The tests check software behavior, not a measured handwriting-accuracy rate. Installation details, fixture requirements, and baseline procedures are in [testing](docs/testing.md).

Further work should consolidate reviewed examples from the established Gemini workflow before broader architectural changes. The reading instructions already live in `egg_slip_prompt.py`, and usage accounting lives in `token_usage.py`; most selection, execution, validation, and reporting still reside in `transcribe.py`. A reusable archival backend is planned, but additional document domains are not implemented.

| Documentation | Use it for |
| --- | --- |
| [Configuration](docs/configuration.md) | Credentials, profiles, request limits, retries, and usage estimates. |
| [Input and filename rules](docs/filename_rules.md) | Catalogue columns, paths, target scope, and physical-card grouping. |
| [Transcription and output rules](docs/transcription_rules.md) | Source fidelity, collector guidance, review markers, missing-card blocks, reports, and reuse. |
| [Testing](docs/testing.md) | Offline regression checks, optional live checks, and reviewed reference material. |
| [Project handoff](docs/PROJECT_HANDOFF.md) | Current responsibilities, development decisions, history, and remaining work. |
| [Contributor instructions](AGENTS.md) | Data protection and implementation requirements. |

## Related projects

This project is part of a set of tools supporting the museum egg-collection workflow:

- [museum-scanner](https://github.com/erl67/museum-scanner) organizes scanned slips, applies consistent filenames, and prepares JPEG and TIFF derivatives.
- [museum-collection-analysis](https://github.com/erl67/museum-collection-analysis) provides notebooks, graphs, and maps for exploring collection dates, collectors, and geographic patterns.

## Collection materials and licence

Source code in this repository is licensed under the **Apache License 2.0**. A standalone `LICENSE` file has not yet been added. Sample collection images, specimen records, and other third-party materials retain their own rights and usage restrictions.

The full production collection and credentials are supplied locally. The repository contains selected sample JPEGs and some previously tracked reference reports; new test reports are ignored by default. Review actual staged files before publishing collection material: ignore rules do not remove files already tracked by Git, and custom output locations may require their own exclusions.
