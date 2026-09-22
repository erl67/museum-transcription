# Historical revision notes

Preserved from the Work development conversation. The original notes below are retained; older sections describe earlier builds and may be superseded. For current setup and behavior, use [README.md](README.md) and [docs](docs/configuration.md); for decisions and the migration state, use [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md). Current code and tests remain authoritative. Dated provider guidance here is historical context, not a current model-availability or quota guarantee.

In particular, earlier statements that console-only mode writes no files predate daily usage accounting: it now writes the quota counter/lock, while still creating no transcription reports or journals. Test mode bypasses journals, and its `TEST_TEMPERATURE` overrides profile temperature unless explicitly overridden on the command line.

# Egg-slip transcription revision — 21 September 2026

Current build: **2026-09-21.2**. Normal startup prints this version, the absolute script path, the Python executable, and the selected model's limits. `--version` displays just the version.

## Handpicked test cards and temperature comparisons

There is now a `test` target. Run the script normally and enter `test` at the target prompt, or use `python transcribe.py test`.

The default folders are inside your project, next to `Family` and `scripts`:

| Purpose | Folder |
| --- | --- |
| Handpicked scans | `G:\My Drive\Egg Slip Scanning\tests\inputs` |
| Test reports | `G:\My Drive\Egg Slip Scanning\tests\outputs` |

The first `test` run creates both folders if needed. If the input folder is empty, it tells you where to copy the scans and makes no API requests or empty report. Copy your 10–15 chosen cards' JPG/JPEG files **directly into `inputs`**, keeping their original filenames. Multiple species belong together in this one folder; species subfolders are not needed or searched. Include both A and B when a card has a back. Each A/B pair remains one card and one request before retries. There is no hard limit of 15 cards.

The script extracts each card's E-number(s) from its filenames and looks up those records in the existing master CSV. It does not require the card's normal Family/species folder for a test. Uncatalogued scans are also accepted and appear at the end. An E-number missing from the spreadsheet gets a review warning and is transcribed without unrelated reference hints.

The two settings you change are together near the top:

```python
MODEL = "gemini-3.5-flash-lite"
TEST_TEMPERATURE = 0.1
```

Run `test`, change `TEST_TEMPERATURE` to `1.0`, save the script, and run `test` again. Repeat with another `MODEL` as needed. Each launch runs just the selected combination; it does not automatically launch a temperature sweep. `TEST_TEMPERATURE` only affects `test`, leaving normal species/E-number runs on their existing profile settings. An explicit command-line `--temperature` overrides the code setting for that run. `TEST_TEMPERATURE = None` or `--temperature auto` omits the API temperature parameter for a model that requires its default.

Every run creates a separate report, for example:

```text
test_20260921_1725_g3.5-f-l_t0.1.txt
test_20260921_1726_g3.5-f-l_t1.0.txt
test_20260921_1730_g3.8f_t0.1.txt
```

The timestamp still ends at hours and minutes. Repeating the same settings in the same minute produces `test_20260921_1725_2_g3.5-f-l_t0.1.txt`, then `_3`, preserving every earlier report. The model tags are `g3.5-f-l`, `g3.6f`, and `g3.8f`. Other profiles use their full model ID unless you set their optional `filename_tag`. The report itself records the full model ID and effective temperature, regardless of abbreviation.

**Test runs always make fresh API calls.** They never open, read, or write a transcription cache, including the existing production journals. Repeating the same cards with the same model and temperature still sends new requests. Each card request contains its own images, prompt, and applicable spreadsheet hints; it does not include an earlier test's transcription. You do not need `--force`. Existing species reports and caches remain untouched, and normal targets retain their existing resume behavior.

The persistent **daily request counter still applies** across both tests and normal runs. A test does not reset quota. At 20 requests/day, two temperatures on 10 cards use all 20 requests if none require a retry; two temperatures on 15 cards require at least 30 requests. A quota stop preserves the current test report and marks it stopped. The next `test` starts again at the first card, making a fresh comparison rather than resuming partway through an earlier test.

Useful optional commands:

```powershell
python transcribe.py test --dry-run
python transcribe.py test --model gemini-3.8-flash --temperature 1.0
```

`--dry-run` lists the chosen cards and front/back order without creating folders, reports, cache entries, or quota records, and without API calls. To relocate the test folders, use `--test-input-dir` and `--test-output-dir`; otherwise their location follows the parent of `--base-dir`/`BASE_FAMILY_DIR`, independently of where VS Code starts Python. `test --console-only` is rejected because test mode always saves its report.

This revision preserves the existing transcription prompt and normal-run cache fingerprints. **115 offline regression tests pass**, including mixed-species spreadsheet matching, original A/B ordering, both temperatures on all three Gemini profiles, fresh requests despite an existing production cache, repeated reports, quota stops, and optional OpenAI requests. No live API calls were made.

## One setting for model testing

Change only this line in section 1 of `transcribe.py`, then launch normally:

```python
MODEL = "gemini-3.8-flash"
```

The delivered default remains `gemini-3.5-flash-lite`. The selected entry in `MODEL_PROFILES` supplies the provider, RPM, daily attempt cap, timeout, retry budget, and generation settings together:

| MODEL value | Provider | RPM | Local daily attempt cap | Timeout per request | Attempts per card |
| --- | --- | ---: | ---: | ---: | ---: |
| `gemini-3.5-flash-lite` | Gemini | 15 | 500 | 180 seconds | 5 |
| `gemini-3.6-flash` | Gemini | 5 | 20 | 300 seconds | 3 |
| `gemini-3.8-flash` | Gemini | 5 | 20 | 300 seconds | 3 |
| `gpt-5.6-luna` | OpenAI, optional | 5 | 20 | 300 seconds | 3 |

The Gemini allowances are the ones you supplied. The OpenAI values are conservative **testing caps**, not a claim about your account's quota. A card with front and back images uses one request before retries. The 20-request cap therefore does not guarantee 20 completed cards. Requests remain sequential, spaced at least 4.1 seconds apart for 15 RPM or 12.1 seconds for 5 RPM; a slow request does not incur another full pacing delay afterward.

You can select a profile for one run without editing the file:

```powershell
python transcribe.py Falco_mexicanus --model gemini-3.8-flash
python transcribe.py --list-models
python transcribe.py --model gemini-3.6-flash --check-config
```

`--model` applies the selected profile's defaults just like the settings line. Explicit command-line settings such as `--rpm`, `--rpd`, `--timeout`, and `--attempts` override individual values for that run. An unknown model stops before any requests; add its entry to `MODEL_PROFILES` instead of inheriting another model's limits accidentally. Copy a profile and use the exact model ID as the dictionary key. Choose that provider's supported image, temperature, and thinking/reasoning options. `None` omits an optional generation setting. Gemini's `thinking_level=None` preserves each model's own default; this update keeps your Gemini temperature at 0.1. `gemini-3.8-flash` rejects a locally configured `minimal` thinking level before submitting it because it supports low, medium, and high. [Gemini thinking settings](https://ai.google.dev/gemini-api/docs/thinking)

### Daily accounting and resumable stops

The script creates `transcribe_request_usage.json` beside itself and counts every attempted request **before sending it**, including retries and console-only readings. Counts are separate for each provider/model, shared across targets and restarts, and contain no keys or transcription text. Keep this file when replacing the script. `--quota-file` selects another existing directory's counter file when needed; all runs that share an allowance must use the same file. A damaged or unwritable counter stops before another request rather than silently resetting usage.

Gemini counters reset at midnight Pacific time, with daylight-saving changes handled by timezone data. Google applies quotas per project, not per key. The counter only knows about attempts made by this script using the same counter file: it cannot see earlier versions, other tools, or other machines. It conservatively includes failed and interrupted attempts. Run one batch at a time, since minute pacing is per process. Token-per-minute limits and service capacity can still affect requests. [Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)

At the local cap, the current record receives `STATUS: PAUSED` and the program exits without an overnight wait. Run the same target after the reset: normal targets reuse their completed cache entries, while `test` starts fresh. An API response explicitly identifying daily quota exhaustion also pauses immediately and is remembered for that day. OpenAI's starter profile uses UTC midnight for its **local test cap**, which is separate from OpenAI's account limits. Its insufficient-credit/billing response pauses without pointless retries. Set a profile's `rpd=None` or pass `--rpd 0` only when you deliberately want to remove the local cap; attempt accounting continues.

HTTP 429 normally indicates quota/rate limiting; HTTP 503 means the service is temporarily overloaded or unavailable. The script uses bounded backoff for service errors and at least a minute for a retryable 429, respecting longer server hints. A server-requested delay over the profile's `max_retry_wait` (120 seconds by default) pauses the run instead of waiting indefinitely or retrying early. Repeated transient failures stop the batch, and the model is never replaced automatically. Each request logs its attempt number, local daily count, and timeout so a wait is visible. [Gemini API errors](https://ai.google.dev/gemini-api/docs/api-errors)

### Optional OpenAI testing

The OpenAI Responses API backend is implemented. When ready, install its optional SDK, add a separate key to the same `.env`, and select the OpenAI profile:

```powershell
python -m pip install --upgrade openai Pillow tzdata
```

```dotenv
GEMINI_API_KEY=your_google_key
OPENAI_API_KEY=your_openai_key
```

```python
MODEL = "gpt-5.6-luna"
```

Gemini profiles use only the Google key; OpenAI profiles use only `OPENAI_API_KEY`. OpenAI receives the same labelled images and transcription instructions through its own API. The starter profile omits temperature and reasoning overrides and requests original image detail, which the current model supports. Both providers use the same front/back, plain-text, and response-completeness checks. Incomplete OpenAI responses are saved for inspection and never accepted as completed cards. [OpenAI image inputs](https://developers.openai.com/api/docs/guides/images-vision), [Responses API](https://developers.openai.com/api/reference/python/resources/responses/methods/create)

SDK-level automatic retries are disabled for both providers; every retry goes through this script's pacing and daily counter. OpenAI output-token usage includes reasoning, so the journal separates reasoning from answer tokens to match its existing Gemini usage fields. For OpenAI, billed output tokens correspond to `candidates_token_count + thoughts_token_count`.

### Existing results and installation

For normal species/E-number/range runs, the model-profile update does **not** change the transcription prompt or default Gemini generation settings. Matching Gemini results from build 2026-09-18.1 remain reusable. Changing just RPM, RPD, timeout, or retry settings does not request them again. Changing the model or a generation setting creates separate cache entries; switching back reuses that model's earlier matching results. Reports identify the provider/model under each card's FILES line. The `test` target described above always bypasses this cache.

Update dependencies once on the Windows Python installation that runs this script; `tzdata` supplies Pacific-time rules:

```powershell
python -m pip install --upgrade google-genai Pillow tzdata
```

The initial model-profile build passed **103 offline tests**, including both real SDKs with simulated HTTP transports, five-RPM pacing, persistent daily caps, Pacific reset boundaries, quota pauses, retry accounting, model switching, and preserving existing transcription behavior. The test-folder build adds 12 checks, bringing the current total to 115. No live Gemini or OpenAI requests were made. Windows-specific locking and your account's active quotas still require running on your machine.

## Uncatalogued scans, signatures, measurements, and plain text

Species runs now include JPEGs named like `Falco_mexicanus_Uncatalogued01(A).jpg` and `(B).jpg`, even though they have no spreadsheet record. `Uncataloged` is also accepted, case-insensitively, with optional numeric identifiers. A/B sides form one card and are sent in front/back order; an unlettered file or a lone A is front-only. Uncatalogued groups appear after all selected E-numbered cards, in natural filename order (01, 02, 10). Each source filename appears between equals signs in the header, one banner per supplied side, followed by one combined transcription. No CM number is invented.

CSV row-range runs include the uncatalogued scans in each species folder visited by that selection. A single E-number or E-number* lookup still selects only that numbered card. For example, use `python transcribe.py Falco_mexicanus --dry-run` to see the groups without API calls, then run the same species normally. Unknown filenames that do not match the numbered or explicit uncatalogued naming patterns are still reported for correction. Species folders still use the existing CSV Family mapping.

Uncatalogued cards receive no unrelated CSV hints and use the same retries and side checks as numbered cards. Normal runs journal and reuse matching results; changing either side refreshes that pair. Test mode requests every card again on every run.

The signature instructions now explicitly allow the visible initials and strokes to be interpreted using the collection heading, narrative, and available catalogue hints. Your identified `H. W. Brandt` signature is a known reading candidate on Brandt forms. It is not inserted automatically into every Brandt card. A name that remains inferred is bracketed, with a short explanation in TRANSCRIPTION NOTES; a truly empty Collector field stays empty.

Grouping braces are treated as layout. Each diameter/depth group keeps its own inside/outside entries, for example the unfilled printed measurement fields on E5184:

```text
Nest: Diameter: Inside: - inches; Outside: - inches
Depth: Inside: - inches; Outside: - inches
```

A note spanning those blank fields goes in ANNOTATIONS with its location. Measurements in the narrative do not fill blank printed fields automatically. The instructions retain the earlier expansion of clear ditto marks.

Fractions and set marks must be ordinary text (`5/4`, `1 1/2`), and multiline fields must use actual line breaks. LaTeX commands, equation environments, and math wrappers trigger the existing single format retry, which rereads the original images. The script does not turn a stacked measurement pair into a quotient or discard mathematical-looking text. If the retry still contains detected LaTeX, the record is marked FAILED with the response saved for inspection, not cached as a successful transcription. All four reported LaTeX examples are covered by regression tests.

**The September 18 update changed the transcription prompt.** Cards cached before that prompt change are transcribed again once to apply the signature and layout rules. Matching September 18 results are reusable in the September 21 update. Existing reports remain unchanged; there is no need to delete the cache or use `--force`.

All **83 offline regression tests passed**, including uncatalogued grouping, ordering, headers, selected-run scope, cache reuse, changed-side refresh, and bounded LaTeX retries. Both attached Falco scans were visually inspected. The new handwriting instructions have not been tested through a live Gemini request.

## Back-heading validation fix — build 2026-09-16.5

The E4936 response contained a back under `SECTION: BACK OF SLIP`. The validator previously required `BACK OF SLIP:` and incorrectly reported zero backs. Both forms now work, including standalone headings without a trailing colon, Markdown headings, and numbered additional backs. The response text is preserved. Missing, empty, duplicated, out-of-order, and truncated back responses still fail validation.

A failed response is now introduced by `SAVED RESPONSE (see error above):`; a validation failure alone does not establish that the response was cut off. Inspect the error for the actual reason.

The 2026-09-16.5 fix did not change the prompt or invalidate successful cached results. Failed cards were retried automatically, while matching successful cached cards were reused. See the current update above for its prompt change. Existing text reports are not rewritten.

All 74 offline regression tests passed, including the reported heading pattern, preservation of both sides and their annotations without a retry, numbered backs, and rejection of missing/empty/duplicate/cut-off backs. Tests use simulated responses, not live Gemini requests; they do not verify handwriting accuracy.

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

## Key lookup, authentication, and shorter filenames

Save this download over `G:\My Drive\Egg Slip Scanning\scripts\transcribe.py`, the exact file your VS Code command runs. A separate download named `transcribe (1).py` does not update that file. Confirm `Egg-slip transcriber 2026-09-18.1` at the beginning of the next run.

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
- A format retry adds explicit corrective instructions about the actual images and logs that there is one format retry. The overall request-attempt limit now comes from the selected profile; service errors and format errors have different retry budgets.

The pasted example is E15, whereas the duplicate-annotation error names E4933. The pasted E15 text itself passes both the old and corrected validators. The two reported messages were reproduced with an extra empty back template and with one annotation heading on each side; E4933's exact failed response was not supplied.

## Start using it

1. Save your existing script as a backup and put the new `transcribe.py` in its place. The two path settings remain near the top.
2. For Gemini, install/update dependencies with `python -m pip install --upgrade google-genai Pillow tzdata`. OpenAI support additionally needs `openai`. Python 3.10 or later is required.
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

To resume a normal run, rerun the same target. A broader or overlapping range can also reuse earlier completed cards. Each run produces a fresh readable report for the selected cards, so the report is usable without merging old files. Old text reports are not imported into the journal. Prompt changes, including the 2026-09-18.1 update, cause selected cards to be transcribed again once with the new instructions. Subsequent matching normal runs reuse those results. Failed entries are always retried. You do not need to delete old outputs or the cache, or add `--force`, to apply these fixes. The separate `test` target always starts fresh.

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
| `python transcribe.py "2-1000"` | Saves/reuses cards selected by CSV rows, plus uncatalogued scans in each visited species folder; row 2 is the first data row. |
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

Request spacing and daily caps now come from the selected profile, as described above. The default Flash-Lite profile keeps 4.1-second spacing; the two Flash profiles use 12.1 seconds. Console-only runs still save daily attempt counts even though they create no reports or transcription cache entries.

Common filename forms include `Species_E123.jpg`, `Species_E123(A).jpg`, `Species_E123(B).jpg`, and `Species_E123_E124(A).jpg`. The optional `_exchanged` tag may follow the E-number or side suffix, before `.jpg`/`.jpeg`. Numeric side suffixes sort numerically. The script also accepts `_A`, `-A`, and `-A-` suffixes. An unlettered front plus an `(A)` front in the same group is ambiguous and is reported instead of automatically submitting both, including tagged duplicates. A lone `(B)` is labelled as a back with a missing-front warning. A lone unlettered or `(A)` image is a complete front-only input, without a missing-back warning.

The timeout and total-attempt limit come from the selected profile. A malformed/empty response gets at most one format retry within that budget. An output-token cutoff is retained as a failure with its saved text, requiring a higher cap on a later run. Persistent service failures stop the run so you can resume later.

## What the three samples established

- E4268(A) and E4268(B) form one front/back group. The back is continuous narrative with paragraphs, abbreviations, and a sex symbol, not another copy of the front's printed fields.
- E4268(A) includes a changed scientific-name entry and a stamped catalogue number. Those need to remain distinct from the current CSV name and filename.
- E4927 includes a collection heading, blue stamp, handwritten corrections, nested printed dimensions, blanks, and extensive lower-page handwriting. A transcription that looks tidy can still omit information; those details need inspection.

No historical spelling or handwritten word was “corrected” in the photographs. They served as visual design examples and real input files for the offline tests, not as a fabricated accuracy benchmark.

## Validation and limits

The current 2026-09-21.2 build passes all 115 offline tests. The first September 21 build passed 103; the September 18 build passed 83. These check program behavior using simulated API responses; they do not measure transcription accuracy on signatures or faint handwriting. The Falco images were inspected as examples of the intended layout and signature instructions, without altering the scans.

The SOP update passed all 71 existing offline regression checks. Direct output checks also verified aligned CM headers for different number lengths, preservation of leading zeros, shared-slip headers, and two blank lines between records. The new prompt has not been evaluated against live Gemini responses.

71 offline regression tests passed: all 69 previous checks plus tests of empty-note markers and correction of cached review flags while preserving genuine notes and other warnings. The latest checks cover local-file precedence, process fallback, alternate key-file forms, hidden `.txt` extensions, version/config diagnostics, stopping without an unexpected prompt, fatal malformed-file handling, actual SDK endpoint/header selection despite conflicting environment settings, and preserving same-minute reports. Earlier tests cover the exact pasted E15 text, multiple annotations and per-side headings, front-only placeholders, supplied blank backs, `_exchanged` filenames, corrective retries, `.env` encoding/lookup from an unrelated launch directory, client initialization, the supplied three JPEGs, source-byte preservation, actual SDK serialization through an in-memory HTTP transport, front/back ordering, shared E-number selection, changed-input invalidation, cache reuse, partial-journal recovery, output-write failure after checkpointing, quota retries, and response validation. The saved `test_transcribe.py` can be run with:

```powershell
python -m unittest -v test_transcribe.py
```

The optional scan test requires `EGG_SLIP_SAMPLE_DIR` to point to the folder containing the three supplied Accipiter JPEGs. Without it, that one test is skipped. Provider SDK tests are skipped if their SDK is not installed. No test uses a real key or real API endpoint.

The actual Windows Google Drive mount, Windows locking branch, complete master CSV, account quotas, and live model responses were not available for execution here. The prompt changes are intended to improve fidelity; no percentage improvement in handwriting accuracy has been measured. The default temperature remains your working 0.1 so that temperature tuning can be compared separately.

Google recommends exponential backoff, jitter, and selective retries for transient failures; the SDK also has its own retries, which this script disables so it can pace every attempt itself. [Gemini troubleshooting guide](https://ai.google.dev/gemini-api/docs/troubleshooting)

Google's Gemini 3 guidance recommends temperature 1.0 and trying higher media resolution for dense documents. That is a useful A/B test on these slips, not evidence that 1.0 has already outperformed your current setting. [Gemini 3 developer guide](https://ai.google.dev/gemini-api/docs/gemini-3)

The API's inline image request limit is 20 MB including other request content. The script estimates the encoded payload and stops before exceeding its conservative 19 MB budget, with a suggested resize option. [Image input documentation](https://ai.google.dev/gemini-api/docs/image-understanding)
