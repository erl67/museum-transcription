# Egg-slip transcription revision — 16 September 2026

Current build: **2026-09-16.4**. Normal startup prints this version, the absolute script path, and the Python executable. `--version` displays just the version.

Build 2026-09-16.3 fixed false review flags for `TRANSCRIPTION NOTES: None.` (also `None`, `N/A`, and `-`). The text is preserved. Cached results receive the same status correction locally, retaining any other review flags and making no new API request.

## SOP formatting — build 2026-09-16.4

Each slip begins with a banner such as:

```text
======================CM1972======================
```

`CM` starts in column 23 on every banner, with the number starting in column 25. The right-hand equals padding adjusts for the number's length; leading zeros are preserved. A shared slip with multiple E-numbers gets one aligned CM banner per number, followed by a single transcription. The existing ID, STATUS, FILES, and review metadata remain beneath the banner. There are now two blank lines between slips.

The transcription instructions now require the full visible collection heading as the first line of the transcription body, followed by fields in `Label: value` form, one field per line. The supplied example reads **COLLECTION OF WILSON C. HANNA**; other cards must use their own visible heading. A separate catalogue stamp belongs in ANNOTATIONS rather than being appended to Set No. or Collector.

Clear ditto marks may be expanded using their own column or field context. For the example card, the two depth labels become `Depth outside: 1.9 in.` and `Depth inside: 1.1 in.`. Ambiguous ditto marks remain literal with an explanatory note. Ordinary quotation marks, unit symbols, historical spellings, and other card wording are preserved.

The human transcription supplies formatting guidance, not replacement text for other cards. No particular collection heading, crossed-out number, or example measurement is inserted automatically into model output. The banner and inter-slip spacing are formatted by Python; reading headings and resolving ditto marks remain image-transcription tasks for Gemini.

The revised `transcribe.py` keeps `gemini-3.5-flash-lite`, your two existing Windows paths, temperature 0.1, dynamic plain-text fields, and the original species / E-number / E-number* / CSV row-range inputs. It reads the master CSV and source photographs without modifying either.

## Latest update: key lookup, authentication, and shorter filenames

Save this download over `G:\My Drive\Egg Slip Scanning\scripts\transcribe.py`, the exact file your VS Code command runs. A separate download named `transcribe (1).py` does not update that file. Confirm `Egg-slip transcriber 2026-09-16.4` at the beginning of the next run.

The latest submitted log showed HTTP **401**, not 404. It also lacked the preceding key-source or missing-file messages that the previous revision always printed, suggesting an older script was running. The new banner makes the running copy identifiable.

This build gives local `.env` files precedence over old terminal environment values. It prints the key's source, never the value. Missing keys and unusable `.env` files stop with a specific setup error; manual entry is available only when explicitly enabled with `--prompt-key`. The client explicitly uses the Gemini Developer API endpoint and key header, ignoring unrelated Vertex/Enterprise backend or Gemini base-URL environment settings.

An HTTP 401 means Google rejected the submitted credential; local file discovery does not establish that the key is valid. Google documents a September 2026 transition away from Standard keys. If 401 persists after the new script loads the intended file, check the **Key Type** in AI Studio and use an **Auth** key from the intended project. This is a documented possibility, not a confirmed diagnosis of the reported credential. [Google's API key and migration documentation](https://ai.google.dev/gemini-api/docs/api-key#migrate-to-an-auth-key)

Report timestamps now stop at minutes: `Accipiter_cooperii_transcriptions_20260916_0825.txt`. Another run in the same minute creates `_0825_2.txt`, then `_0825_3.txt`, preserving earlier files. Seconds and microseconds are no longer used in report filenames.

## Fixes for the reported failures

- The previous revision read process environment variables but did not load `.env` files. This version loads the key from `.env` without adding a dependency, even when VS Code starts Python from `C:\Program Files\Microsoft VS Code`.
- Each request now states the actual number of front and back images. `E123.jpg` or a lone `E123(A).jpg` is front-only and does not need a back. An A/B pair is one card with two supplied sides.
- A front-only response containing a clearly empty back placeholder (such as an empty `BACK OF SLIP:` or `[blank]`) is retained with that placeholder removed and a review note. Substantive unexpected back text is never silently deleted. A supplied back still must be present in the response.
- `ANNOTATIONS:` can occur within each side. Multiple location entries are valid. Repeated headings within the same side retain all text and produce a review flag rather than failing the card.
- The exact reported filenames `Accipiter_Cooperii_E3024(A)_exchanged.jpg`, `Accipiter_Cooperii_E3024(B)_exchanged.jpg`, and `Accipiter_Cooperii_E4314_exchanged.jpg` now match. `_exchanged` is a filename tag, not another side; filenames remain in the output header.
- A format retry now adds explicit corrective instructions about the actual images and logs that there is one format retry. The overall request-attempt limit remains five; service errors and format errors have different retry budgets.

The pasted example is E15, whereas the duplicate-annotation error names E4933. The pasted E15 text itself passes both the old and corrected validators. The two reported messages were reproduced with an extra empty back template and with one annotation heading on each side; E4933's exact failed response was not supplied.

## Start using it

1. Save your existing script as a backup and put the new `transcribe.py` in its place. The two path settings remain near the top.
2. The dependencies are still `google-genai` and `Pillow`. If necessary, update them with `python -m pip install --upgrade google-genai Pillow`. Python 3.10 or later is required.
3. Run `python transcribe.py` and enter a target as before.
4. Put `.env` beside the script at `G:\My Drive\Egg Slip Scanning\scripts\.env`, or in `G:\My Drive\Egg Slip Scanning\.env`, with this line:

```dotenv
GEMINI_API_KEY=your_actual_key_here
```

The file must be named `.env`, not `.env.txt`; a hidden `.txt` extension is reported explicitly. `GOOGLE_API_KEY` and `API_KEY` assignments also work in the file. A file containing only one Google key beginning with `AIza` or `AQ.` is accepted as well; the named assignment above is recommended. Simple quoted values, `export`, comments, UTF-8 with or without a BOM, and BOM-marked UTF-16 files are supported. This is a key-only reader: it does not execute commands, expand variables, or load unrelated settings into the environment. No `python-dotenv` installation is needed.

Lookup order is: `.env` beside the script, its parent folder, the master CSV folder, the parent of the configured Family directory, and the current working directory. Duplicate paths are checked once. The first existing file must contain a usable key, or the script stops and identifies that file. Within it, the name preference is `GEMINI_API_KEY`, `GOOGLE_API_KEY`, then `API_KEY`. If no `.env` file exists, nonempty process `GEMINI_API_KEY` and then `GOOGLE_API_KEY` are checked. `--env-file "G:\path\to\.env"` selects a specific required file instead of the default search. A selected file takes precedence over terminal environment variables.

The script prints where it found the key without printing the key itself. There is no automatic key prompt. `--prompt-key` enables a hidden prompt only if no file or process key is found; the script does not save manual input. A malformed existing file must be corrected first.

To check the running copy and key lookup without reading the CSV, transcribing a card, or sending an API request, run:

```powershell
& C:\Users\E\AppData\Local\Microsoft\WindowsApps\python3.13.exe "G:\My Drive\Egg Slip Scanning\scripts\transcribe.py" --check-config
```

Success here confirms local lookup only; Google has not validated the credential.

The supplied original contained an API key. Replace that key in Google AI Studio; the revised file does not contain it. This review did not use it or make any real Gemini requests.

For an initial check, use the examples below. Console-only mode makes fresh requests even when a saved result exists, and writes no transcription, checkpoint, or lock files.

```powershell
python transcribe.py "E4268*"
python transcribe.py "E4927*"
```

`E4268` should send A as the front and B as the back. `E4927` is the useful dense-handwriting check. After reviewing them, launch a normal saved batch:

```powershell
python transcribe.py "2-1000"
```

## Changes and why they matter

| Area | Problem in the original | Revised behavior |
|---|---|---|
| Front/back order | `os.listdir()` order was used without sorting. | Orders A/B/C and numeric sides explicitly and labels every image in the request. |
| Shared slips | Selection and CSV lookup used only the first E-number in a filename. | Matches any complete E-number, submits the shared image group once, and includes separate hints for all available records. `E18` never matches `E187`. |
| Historical wording | CSV values were called “GROUND TRUTH.” | References are explicitly fallible hints. Visible wording, historical taxonomy, blanks, stamps, and corrections take precedence. Hints can also be disabled. |
| Complex cards | Unreadable text could become a plausible unmarked guess. | Distinguishes uncertain readings, illegible text, and blank fields; emphasizes sublabels, printed units, symbols, collection headings, additions, and dense lower lines. These are model instructions, not a guarantee of accuracy. |
| Restarting | Every launch requested every selected card again. | Reuses completed results whose submitted image bytes, image order/names, prompt, relevant hints, model, and generation settings match. |
| Failed requests | Error text was saved in the same place as a normal transcription. | Marks failures explicitly, preserves available partial responses, and retries failed cards on the next run. |
| Incomplete responses | `.text.strip()` assumed a usable complete answer. | Checks finish reason, answer text, required sections, section order, and supplied back sections. Cut-off output is not cached as completed. |
| Quota and outages | Retries and fixed sleeps were separate, and some transient errors were missed. | Paces every attempt, uses bounded exponential backoff, honors server retry hints, and stops after persistent rate/network/server failure. Authentication, model, and request-configuration errors stop immediately. |
| Images | Every image was capped at 2,000 pixels on its longest edge. | Keeps original JPEG bytes/resolution when possible, honors EXIF orientation, and offers an optional resize cap. Your supplied scans are already roughly 2,048 pixels, so their resolution gain is small. |
| CSV/folders | Duplicate E-numbers silently replaced earlier rows; paths assumed one layout. | Retains duplicates, rejects conflicting routing, validates required columns, supports case-insensitive lookup and both existing folder layouts. |
| Output collisions | Minute-resolution filenames could append unrelated runs together. | Every run creates a separate file with a date/hour/minute timestamp; same-minute repeats get a short counter instead of overwriting or appending. |
| Write recovery | Text was flushed but there was no durable reusable checkpoint. | Saves and synchronizes a result to the journal before writing its readable text block. A later text-write failure can reuse that result. |

The prompt stays flexible: it does not impose a species-wide fixed list of fields. Annotations remain separate from printed field values. The text output adds `STATUS`, `FILES`, and optional `REVIEW` lines in each card's header; downstream parsers that assume the old header layout will need adjustment.

## Outputs and resuming

Saved output stays in the family directory, as before. For each species there are:

- `Species_transcriptions_TIMESTAMP.txt`: the readable results for that selection, including reused results and explicitly marked failures.
- `Species_transcriptions_cache.jsonl`: the append-only progress journal. Keep it to retain resumability. Each entry records the result, source paths, catalogue numbers, model, available token counts, and input fingerprint.
- `Species_transcriptions.lock`: a tiny coordination file. The OS releases its lock after the process exits, including a crash. The file itself may remain; that does not mean the lock is still held.

To resume, rerun the same target. A broader or overlapping range can also reuse earlier completed cards. Each run produces a fresh readable report for the selected cards, so the report is usable without merging old files. Old text reports are not imported into the new journal. The SOP update (2026-09-16.4) changes the prompt, so previously cached results for the selected cards are transcribed again once to request the collection headings and ditto expansion. Subsequent matching runs reuse those results normally. Failed entries are always retried. You do not need to delete old outputs or the cache, or add `--force`, to apply these fixes.

`STATUS: OK` means the response passed structural checks. It does **not** mean a human has verified every word. `STATUS: REVIEW` flags bracketed uncertainty, nonempty transcription notes, missing/gapped image sides, removed empty back placeholders, or repeated annotation headings within one side. Review results are retained and reused; run with `--force` to request a fresh reading. `STATUS: FAILED` is never reused as a completed result.

A crash after the API responds but before its journal entry is written can still require one repeated request. A damaged journal line is reported and ignored; intact entries remain usable. The lock coordinates processes on the same computer, not independent computers connected to the same Google Drive account.

## Useful options

| Command | Result |
|---|---|
| `python transcribe.py Accipiter_gentilis --dry-run` | Shows file groups and side order; no API calls, credential prompt, or output files. Does not assess image legibility. |
| `python transcribe.py Accipiter_cooperii --env-file "G:\My Drive\Egg Slip Scanning\.env"` | Reads the key from the specified file, ahead of terminal environment values. |
| `python transcribe.py --check-config` | Displays the running version/path and checks local key loading, without requests or CSV/image reads. |
| `python transcribe.py --version` | Displays the script build number. |
| `python transcribe.py Accipiter_cooperii --prompt-key` | Enables manual hidden key entry when no file/process key is found. |
| `python transcribe.py "2-1000"` | Saves/reuses cards selected by CSV rows, with row 2 as the first data row. |
| `python transcribe.py E4268 --force` | Requests a fresh reading and saves it. |
| `python transcribe.py "E4268*" --no-csv-hints` | Fresh console reading without collector, locality, or taxonomy hints. |
| `python transcribe.py Accipiter_gentilis --console-only` | Fresh console output for a whole species, without result files. |
| `python transcribe.py "2-1000" --rpm 10` | Lowers request pacing to approximately one start every 6.1 seconds. |
| `python transcribe.py E4927 --max-edge 2000` | Restores the original resize cap for that run. |
| `python transcribe.py "E4927*" --temperature 1.0` | Tries Google's recommended Gemini 3 temperature for comparison. |
| `python transcribe.py "E4927*" --media-resolution high` | Optional high-resolution model setting, if supported by the selected model/account. |
| `python transcribe.py E4927 --max-output-tokens 32768` | Raises the response cap if a long response was cut off; subject to the model's limits. |
| `python transcribe.py --help` | Lists all options, including path and model overrides. |

The `*` suffix still means a single E-number. A species/range with `*` now produces an error instead of silently switching into a mode that saves files. Use `--console-only` for those larger selections.

The default request spacing is 4.1 seconds between starts, shared across species and retries in one process. It does not impose an additional 4.1-second sleep after a slow request or after the last result. This limits this process's request rate; token/day quotas and other programs using the same account still apply. Requests remain sequential.

Common filename forms include `Species_E123.jpg`, `Species_E123(A).jpg`, `Species_E123(B).jpg`, and `Species_E123_E124(A).jpg`. The optional `_exchanged` tag may follow the E-number or side suffix, before `.jpg`/`.jpeg`. Numeric side suffixes sort numerically. The script also accepts `_A`, `-A`, and `-A-` suffixes. An unlettered front plus an `(A)` front in the same group is ambiguous and is reported instead of automatically submitting both, including tagged duplicates. A lone `(B)` is labelled as a back with a missing-front warning. A lone unlettered or `(A)` image is a complete front-only input, without a missing-back warning.

The code sets a 180-second request timeout and allows five total attempts. A malformed/empty response gets at most one format retry within that budget. An output-token cutoff is retained as a failure with its partial text, requiring a higher cap on a later run. Persistent service failures stop the run so you can resume later.

## What the three samples established

- E4268(A) and E4268(B) form one front/back group. The back is continuous narrative with paragraphs, abbreviations, and a sex symbol, not another copy of the front's printed fields.
- E4268(A) includes a changed scientific-name entry and a stamped catalogue number. Those need to remain distinct from the current CSV name and filename.
- E4927 includes a collection heading, blue stamp, handwritten corrections, nested printed dimensions, blanks, and extensive lower-page handwriting. A transcription that looks tidy can still omit information; those details need inspection.

No historical spelling or handwritten word was “corrected” in the photographs. They served as visual design examples and real input files for the offline tests, not as a fabricated accuracy benchmark.

## Validation and limits

The SOP update passed all 71 existing offline regression checks. Direct output checks also verified aligned CM headers for different number lengths, preservation of leading zeros, shared-slip headers, and two blank lines between records. The new prompt has not been evaluated against live Gemini responses.

71 offline regression tests passed: all 69 previous checks plus tests of empty-note markers and correction of cached review flags while preserving genuine notes and other warnings. The latest checks cover local-file precedence, process fallback, alternate key-file forms, hidden `.txt` extensions, version/config diagnostics, stopping without an unexpected prompt, fatal malformed-file handling, actual SDK endpoint/header selection despite conflicting environment settings, and preserving same-minute reports. Earlier tests cover the exact pasted E15 text, multiple annotations and per-side headings, front-only placeholders, supplied blank backs, `_exchanged` filenames, corrective retries, `.env` encoding/lookup from an unrelated launch directory, client initialization, the supplied three JPEGs, source-byte preservation, actual SDK serialization through an in-memory HTTP transport, front/back ordering, shared E-number selection, changed-input invalidation, cache reuse, partial-journal recovery, output-write failure after checkpointing, quota retries, and response validation. The saved `test_transcribe.py` can be run with:

```powershell
python -m unittest -v test_transcribe.py
```

The optional scan test requires `EGG_SLIP_SAMPLE_DIR` to point to the folder containing the three supplied JPEGs. Without it, that one test is skipped. The SDK transport test is skipped if `google-genai` is not installed. No test uses a real key or real Gemini endpoint.

The actual Windows Google Drive mount, Windows locking branch, complete master CSV, account quotas, and live model responses were not available for execution here. The prompt changes are intended to improve fidelity; no percentage improvement in handwriting accuracy has been measured. The default temperature remains your working 0.1 so that temperature tuning can be compared separately.

Google recommends exponential backoff, jitter, and selective retries for transient failures; the SDK also has its own retries, which this script disables so it can pace every attempt itself. [Gemini troubleshooting guide](https://ai.google.dev/gemini-api/docs/troubleshooting)

Google's Gemini 3 guidance recommends temperature 1.0 and trying higher media resolution for dense documents. That is a useful A/B test on these slips, not evidence that 1.0 has already outperformed your current setting. [Gemini 3 developer guide](https://ai.google.dev/gemini-api/docs/gemini-3)

The API's inline image request limit is 20 MB including other request content. The script estimates the encoded payload and stops before exceeding its conservative 19 MB budget, with a suggested resize option. [Image input documentation](https://ai.google.dev/gemini-api/docs/image-understanding)
