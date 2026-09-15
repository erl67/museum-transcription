# Egg-slip transcription revision — 15 September 2026

The revised `transcribe.py` keeps `gemini-3.5-flash-lite`, your two existing Windows paths, temperature 0.1, dynamic plain-text fields, and the original species / E-number / E-number* / CSV row-range inputs. It reads the master CSV and source photographs without modifying either.

## Start using it

1. Save your existing script as a backup and put the new `transcribe.py` in its place. The two path settings remain near the top.
2. The dependencies are still `google-genai` and `Pillow`. If necessary, update them with `python -m pip install --upgrade google-genai Pillow`. Python 3.10 or later is required.
3. Run `python transcribe.py` and enter a target as before.
4. If no `GEMINI_API_KEY` or `GOOGLE_API_KEY` environment variable is set, the script asks for the API key at a hidden prompt. Pasting a key there will not display characters; press Enter afterward. The script does not save it.

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
| Output collisions | Minute-resolution filenames could append unrelated runs together. | Every run creates a separate file with a timestamp including microseconds. |
| Write recovery | Text was flushed but there was no durable reusable checkpoint. | Saves and synchronizes a result to the journal before writing its readable text block. A later text-write failure can reuse that result. |

The prompt stays flexible: it does not impose a species-wide fixed list of fields. Annotations remain separate from printed field values. The text output adds `STATUS`, `FILES`, and optional `REVIEW` lines in each card's header; downstream parsers that assume the old header layout will need adjustment.

## Outputs and resuming

Saved output stays in the family directory, as before. For each species there are:

- `Species_transcriptions_TIMESTAMP.txt`: the readable results for that selection, including reused results and explicitly marked failures.
- `Species_transcriptions_cache.jsonl`: the append-only progress journal. Keep it to retain resumability. Each entry records the result, source paths, catalogue numbers, model, available token counts, and input fingerprint.
- `Species_transcriptions.lock`: a tiny coordination file. The OS releases its lock after the process exits, including a crash. The file itself may remain; that does not mean the lock is still held.

To resume, rerun the same target. A broader or overlapping range can also reuse earlier completed cards. Each run produces a fresh readable report for the selected cards, so the report is usable without merging old files. Old text reports are not imported into the new journal: the first run under this version transcribes its selected cards.

`STATUS: OK` means the response passed structural checks. It does **not** mean a human has verified every word. `STATUS: REVIEW` flags bracketed uncertainty, nonempty transcription notes, or missing/gapped image sides. Review results are retained and reused; run with `--force` to request a fresh reading. `STATUS: FAILED` is never reused as a completed result.

A crash after the API responds but before its journal entry is written can still require one repeated request. A damaged journal line is reported and ignored; intact entries remain usable. The lock coordinates processes on the same computer, not independent computers connected to the same Google Drive account.

## Useful options

| Command | Result |
|---|---|
| `python transcribe.py Accipiter_gentilis --dry-run` | Shows file groups and side order; no API calls, credential prompt, or output files. Does not assess image legibility. |
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

Common filename forms include `Species_E123.jpg`, `Species_E123(A).jpg`, `Species_E123(B).jpg`, and `Species_E123_E124(A).jpg`. Numeric side suffixes sort numerically. The script also accepts `_A`, `-A`, and `-A-` suffixes. An unlettered front plus an `(A)` front in the same group is ambiguous and is reported instead of automatically submitting both. A lone `(B)` is labelled as a back with a missing-front warning.

The code sets a 180-second request timeout and allows five total attempts. A malformed/empty response gets at most one format retry within that budget. An output-token cutoff is retained as a failure with its partial text, requiring a higher cap on a later run. Persistent service failures stop the run so you can resume later.

## What the three samples established

- E4268(A) and E4268(B) form one front/back group. The back is continuous narrative with paragraphs, abbreviations, and a sex symbol, not another copy of the front's printed fields.
- E4268(A) includes a changed scientific-name entry and a stamped catalogue number. Those need to remain distinct from the current CSV name and filename.
- E4927 includes a collection heading, blue stamp, handwritten corrections, nested printed dimensions, blanks, and extensive lower-page handwriting. A transcription that looks tidy can still omit information; those details need inspection.

No historical spelling or handwritten word was “corrected” in the photographs. They served as visual design examples and real input files for the offline tests, not as a fabricated accuracy benchmark.

## Validation and limits

38 offline regression tests passed on Python 3.12.14 with `google-genai` 2.23.0. Tests included the supplied three JPEGs, source-byte preservation, actual SDK serialization through an in-memory HTTP transport, front/back ordering, shared E-number selection, changed-input invalidation, cache reuse, partial-journal recovery, output-write failure after checkpointing, quota retries, and response validation. The saved `test_transcribe.py` can be run with:

```powershell
python -m unittest -v test_transcribe.py
```

The optional scan test requires `EGG_SLIP_SAMPLE_DIR` to point to the folder containing the three supplied JPEGs. Without it, that one test is skipped. The SDK transport test is skipped if `google-genai` is not installed. No test uses a real key or real Gemini endpoint.

The actual Windows Google Drive mount, Windows locking branch, complete master CSV, account quotas, and live model responses were not available for execution here. The prompt changes are intended to improve fidelity; no percentage improvement in handwriting accuracy has been measured. The default temperature remains your working 0.1 so that temperature tuning can be compared separately.

Google recommends exponential backoff, jitter, and selective retries for transient failures; the SDK also has its own retries, which this script disables so it can pace every attempt itself. [Gemini troubleshooting guide](https://ai.google.dev/gemini-api/docs/troubleshooting)

Google's Gemini 3 guidance recommends temperature 1.0 and trying higher media resolution for dense documents. That is a useful A/B test on these slips, not evidence that 1.0 has already outperformed your current setting. [Gemini 3 developer guide](https://ai.google.dev/gemini-api/docs/gemini-3)

The API's inline image request limit is 20 MB including other request content. The script estimates the encoded payload and stops before exceeding its conservative 19 MB budget, with a suggested resize option. [Image input documentation](https://ai.google.dev/gemini-api/docs/image-understanding)
