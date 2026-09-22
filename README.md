# Museum Transcription

Large language model assisted transcription of historical museum egg-collection slips. The current application reads JPEG scans, groups the sides of each physical slip, matches catalogue references from a CSV, and produces readable UTF-8 plain-text transcriptions with source filenames and review flags.

This project grew out of a natural-history collection workflow involving roughly 10,000 slips and 12,000 images. Vision models do the reading; Python handles selection, image order, requests, validation, progress, and output. The output uses the fields actually printed on each card, not a fixed database schema.

**Current scope:** a specialized egg-slip application. **Architectural direction:** separate its collection-specific rules from a reusable archival-document transcription backend. Other document collections and a general domain interface are not implemented yet.

## What it does

- Selects a species, an exact E-number, or a range of spreadsheet rows.
- Groups A/B and numbered sides into one request, including shared slips with multiple E-numbers.
- Includes explicitly named uncatalogued scans at the end of species/test reports.
- Uses catalogue values as fallible reading hints; preserves historical wording, spelling, units, and uncertainty.
- Supports Gemini and an optional OpenAI Responses API adapter through model profiles.
- Paces and counts every request attempt, with bounded retries and resumable normal runs.
- Saves independent model/temperature comparisons through a mixed-species `tests` target.
- Keeps source scans and the catalogue CSV read-only.

## Requirements and installation

Python **3.10+**. The primary deployment is Windows with a Google Drive filesystem mount; paths are configurable. Linux is used for offline verification. No Excel application, Tesseract, or `python-dotenv` is required.

From the repository root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

On macOS/Linux, activate with `source .venv/bin/activate`. For OpenAI support and all provider transport tests, also run:

```text
python -m pip install -r requirements-openai.txt
```

These files pin the direct dependencies used for handoff verification; they are not a complete transitive lockfile. `tzdata` supplies the Pacific-time rules needed by Gemini's local daily counter, including on Windows.

Copy `.env.example` to `.env` **beside `transcribe.py`**, and enter the key for the selected provider. Keep it out of Git. Local `.env` files take precedence over process environment variables. `--check-config` checks lookup only, not whether the provider accepts the credential:

```text
python transcribe.py --check-config
python transcribe.py --list-models
```

The application requires a UTF-8 CSV export with the exact columns `catalogNumber`, `Scientific Name`, and `Family`. It does not read `.xlsx` files. Optional columns supply collector and locality hints. See [input and filename rules](docs/filename_rules.md).

## Configure your data paths

The existing defaults in `transcribe.py` point to `G:\My Drive\Egg Slip Scanning` and are environment-specific. Set `CSV_PATH` and `BASE_FAMILY_DIR` for your installation, or pass `--csv` and `--base-dir`:

```powershell
python transcribe.py Accipiter_cooperii --csv "G:\My Drive\Egg Slip Scanning\EggSlipReorganizationProject_FULL.xlsx - Full List.csv" --base-dir "G:\My Drive\Egg Slip Scanning\Family" --dry-run
```

Normal scans belong in `Family/<family>/<Genus_species>/JPEG/` or `Family/<family>/<Genus>/<Genus_species>/JPEG/`. `--base-dir` points to `Family`, not an individual species folder. The CSV determines the family/species routing.

## Usage

Run `python transcribe.py` for the interactive target prompt, or supply a target directly. The following examples assume your paths are configured; the specimen identifiers are usage examples, not promises of bundled data.

| Command | Behavior |
| --- | --- |
| `python transcribe.py Accipiter_cooperii` | Save a species report, including uncatalogued cards. |
| `python transcribe.py E4268` | Select the exact catalogue number; shared slips are submitted once. |
| `python transcribe.py "E4268*"` | Fresh console reading of that card. The star is **not a wildcard**. |
| `python transcribe.py "2-1000"` | Select inclusive CSV row numbers; row 1 is the header. Includes uncatalogued cards in visited species folders. |
| `python transcribe.py Accipiter_cooperii --dry-run` | Preview grouping and side order without API calls or output files. |
| `python transcribe.py E4268 --force` | Refresh a normally cached reading. |
| `python transcribe.py tests` | Run fresh comparisons on the handpicked test folder. |

Normal saved runs reuse completed `OK` and `REVIEW` results only when the input fingerprint matches. Restart the same target after interruption. Console-only mode bypasses transcription caches but still writes daily request counts. `--help` lists the remaining options.

## Model and temperature comparisons

The settings are together near the top of `transcribe.py`:

```python
MODEL = "gemini-3.5-flash-lite"
TEST_TEMPERATURE = 0.1
```

`MODEL_PROFILES` contains the configured model IDs and their provider, limits, generation settings, and retry budgets. These are project settings, not a guarantee of current model availability or account quota. See [configuration](docs/configuration.md).

The curated set in `tests/inputs/` contains **10 cards / 18 images** across several species. Keep all sides directly in that folder. Launch `python transcribe.py` and type **tests**, or run:

```text
python transcribe.py tests --dry-run
python transcribe.py tests --model gemini-3.5-flash-lite --temperature 0.1
python transcribe.py tests --model gemini-3.8-flash --temperature 1.0
```

Only the dry run avoids API calls. The default CSV path remains the configured master CSV. Test input is **tests/inputs beside the script** and the combined report goes to **tests/outputs beside the script**, regardless of the launch directory or Family setting. Override with `--test-input-dir` / `--test-output-dir` if needed. An empty input folder produces no requests or empty report.

Each test runs one configuration, starts at the first card, and **never reads or writes a transcription cache**. Daily limits still apply. Example filenames:

```text
test_20260922_1425_g3.5-f-l_t0.1.txt
test_20260922_1430_g3.8f_t1.0.txt
```

Same-minute repeats get a counter rather than overwriting a report. `TEST_TEMPERATURE` affects only tests; explicit `--temperature` wins. Use `--temperature auto` to omit it. OpenAI profiles are `gpt-5.6-luna`, `gpt-5.6-terra`, `gpt-5.6-sol`, and `gpt-6-astra`; all use `OPENAI_API_KEY` from your existing `.env`. Astra automatically omits the code-level test temperature and uses `tauto` in filenames; an explicit numeric Astra override is rejected before any request.

```text
python transcribe.py tests --model gpt-5.6-luna --temperature auto
python transcribe.py tests --model gpt-5.6-terra --temperature auto
python transcribe.py tests --model gpt-5.6-sol --temperature auto
python transcribe.py tests --model gpt-6-astra
```

The known wollweberi/ultramarina filename mismatch does not prevent the test: catalogue hints are matched by complete E-number. Source names remain unchanged. Full procedures and baseline guidance: [testing](docs/testing.md).

## Output and review

Normal reports and per-species progress journals are written in the **family directory**. Each record has aligned CM banners (or filenames for uncatalogued material), source filenames, model, status, and any review reasons. Two blank lines separate records. Failed responses retain available text for inspection. These are text reports, not spreadsheet updates or a machine-enforced field schema.

`OK` means structural checks passed, not that a person verified the reading. `REVIEW` highlights uncertainty or issues; `FAILED` means the request or response failed checks; `PAUSED` identifies a quota/service stop. Annotation text belongs to the artifact; transcription notes describe reading or interpretation issues. `TRANSCRIPTION NOTES: None` does not itself warrant review. Literal printed brackets can still cause a false uncertainty flag.

See [transcription rules](docs/transcription_rules.md) for preservation, ditto marks, signatures, and front/back handling. Model instructions encourage fidelity but cannot prove that all handwriting was read correctly.

## Development and documentation

```text
python -m unittest -v test_transcribe.py
```

This Windows checkout now runs **115 offline tests: 113 passed, 2 skipped** (the POSIX lock test and the optional older three-image fixture). Both provider SDK transport tests ran, including all four OpenAI profiles. The real curated set also passed a 10-card / 18-image dry run. No live API calls were made. Missing SDKs cause additional skips. Tests use generated fixtures and simulated HTTP transports, never live API credentials. See [testing](docs/testing.md) for exact conditions and limitations.

```text
transcribe.py                  Current application; build 2026-09-22.1
test_transcribe.py             Offline unittest suite
requirements.txt              Gemini/image/timezone dependencies
requirements-openai.txt       Optional OpenAI dependency plus the above
.env.example                  Credential names; no real keys
AGENTS.md                     Durable instructions for coding agents
docs/PROJECT_HANDOFF.md       Architecture, history, invariants, next steps
docs/transcribe_notes.md       Preserved historical revision notes
docs/
    configuration.md          Credentials, profiles, quotas, retries
    filename_rules.md         CSV, paths, targeting, physical-card grouping
    transcription_rules.md    Egg-slip SOP, statuses, reports, caches
    testing.md                Offline tests and live comparison protocol
tests/
    inputs/README.md          Curated JPEG set (10 cards, 18 images)
    outputs/README.md         Combined comparison reports stay local
```

Start future development with [AGENTS.md](AGENTS.md) and [PROJECT_HANDOFF.md](docs/PROJECT_HANDOFF.md). The handoff distinguishes current implementation from the proposed domain/backend extraction. The intended sequence is model comparisons, a reliable egg-slip baseline, then incremental extraction—not a new plugin framework.

## Current limits

The program is sequential, with per-process minute pacing and a local daily counter. It does not track other applications' quota use, enforce token-per-minute limits, calculate costs, or guarantee identical model responses. Windows/Google Drive locking and live model accuracy need deployment testing. A real catalogue and permission-appropriate scans are supplied separately. No accuracy percentage or cross-model winner has been established by this test suite.

Source data and generated results are excluded from Git by default; only deliberately selected JPEGs under `tests/inputs/` are eligible sample scans. Review their publication rights before adding them. No project licence has yet been selected; a public repository is not itself a licence grant.


### Licensce

Source code in this repository is licensed under the Apache License 2.0 unless otherwise noted. Sample collection images, specimen records, and other third-party materials are not covered by the software license and retain their respective rights and usage restrictions.
