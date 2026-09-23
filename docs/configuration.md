# Configuration, providers, and request control

Implementation reference: `ModelProfile`, `MODEL_PROFILES`, `parse_args`, `generation_config`, `Transcriber`, `RateLimiter`, and `DailyQuota` in [transcribe.py](../transcribe.py). These values describe build `2026-09-23.4`; they are not independently verified provider quotas or model-availability promises.

## Profiles and temperature

Change `MODEL` near the top of the script or pass `--model`. The exact ID must have a `MODEL_PROFILES` entry. Unknown profiles fail locally; the application never substitutes a different model/provider after a failure.

| Configured model ID | Provider | RPM | Local daily attempt cap | Request timeout | Total attempts/card | Normal temperature | Test filename tag |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| `gemini-3.5-flash-lite` (default) | Gemini | 15 | 500 | 180 s | 5 | 1.0 | `g3.5-f-l` |
| `gemini-3.6-flash` | Gemini | 5 | 20 | 300 s | 3 | 1.0 | `g3.6f` |
| `gemini-3.8-flash` | Gemini | 5 | 20 | 300 s | 3 | 1.0 | `g3.8f` |
| `gpt-5.6-luna` | OpenAI | 5 | 20 | 300 s | 3 | 1.0 | Full model ID |
| `gpt-5.6-terra` | OpenAI | 5 | 20 | 300 s | 3 | 1.0 | Full model ID |
| `gpt-5.6-sol` | OpenAI | 5 | 20 | 300 s | 3 | 1.0 | Full model ID |
| `gpt-6-astra` | OpenAI | 5 | 20 | 300 s | 3 | Unsupported / omitted | Full model ID |

The Gemini caps came from the maintainer's stated allowances. OpenAI's values are conservative local testing caps, not an account entitlement. Confirm model IDs and supported parameters against the intended account when running live comparisons. The default reflects the established working workflow and available request allowance, not a measured quality ranking.

`ModelProfile.temperature` and `TEST_TEMPERATURE` now default to **1.0**, following the maintainer's chosen operating setting. `TEST_TEMPERATURE` applies only to tests and does not alter normal profiles. Explicit `--temperature` overrides either mode; `--temperature auto` or a Python setting of `None` omits the parameter. Astra retains its unsupported/omitted setting and rejects explicit numeric overrides. An omitted parameter is recorded as `tauto`, never labelled as a temperature that was not sent. Numeric temperatures must be finite and between 0 and 2. Both SDK transports are checked offline; live parameter acceptance for the configured OpenAI models has not been established by these tests.

Profiles also hold `max_output_tokens` (16,384 by default), retry base (5 s for Flash-Lite, 15 s for the other entries), maximum retry wait (120 s), quota timezone, and optional provider generation settings. Explicit CLI options override their corresponding profile values. There is no automatic parameter sweep.

| Setting/flag | Current scope |
| --- | --- |
| `--thinking-level auto/minimal/low/medium/high` | Gemini; omitted by default. The configured 3.8 profile permits only low/medium/high or auto. This is a local profile restriction. |
| `--media-resolution auto/low/medium/high` | Gemini; omitted by default. |
| `--reasoning-effort auto/none/minimal/low/medium/high/xhigh/max` | OpenAI; omitted by default. GPT-5.6 allows none/low/medium/high/xhigh/max; Astra allows low/medium/high/xhigh/max. Unsupported efforts fail locally. |
| `--image-detail auto/low/high/original` | OpenAI; `original` in the current profile. |
| `--max-edge N` | Optional local longest-edge resizing; `0` retains original resolution. |
| `--max-output-tokens N` | Provider output cap; increase deliberately after a token-limit failure. |
| `--rpm`, `--rpd`, `--timeout`, `--attempts`, `--max-retry-wait` | Execution overrides, excluded from transcription cache identity. |

`retry_base`, `quota_timezone`, `filename_tag`, and the configured thinking-level allowlist are profile fields, not separate CLI options. `--rpd 0` / profile `rpd=None` removes the local daily cap but does not disable attempt accounting. `--max-retry-wait` must be at least 60 s. Run `--list-models` or `--help` without any keys or dataset.

Model IDs and reasoning support were checked against [OpenAI's GPT-5.6 guide](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.6). [Astra's guide](https://developers.openai.com/api/docs/guides/latest-model) specifies `gpt-6-astra` and disallows temperature. There is no configured `gpt-5.6-astra` alias. Profiles share the existing Responses transport, completion checks, pacing, and quota code.

## Credentials and `.env`

The small built-in reader loads API keys only; it does not execute shell content, expand variables, or configure arbitrary settings. Supported text encodings are UTF-8 (optional BOM) and BOM-marked UTF-16. Named assignments can be quoted, use `export`, and include comments.

Default `.env` search order:

1. Beside the actual `transcribe.py` file.
2. Its parent directory.
3. The configured CSV's parent directory.
4. The parent of the configured Family directory.
5. The process working directory.

Duplicate paths are checked once. An existing relevant file takes precedence over process environment variables. A malformed, empty, or wrongly named-key file raises an explicit error rather than silently selecting another credential. A file containing only the other provider's valid key can be skipped; a named but empty selected-provider key is still an error. `.env.txt` is diagnosed as a hidden-extension mistake.

`--env-file PATH` replaces the default search list and requires that file to exist. A valid file containing only the other provider's key can still fall through to the selected provider's process environment.

| Provider | File assignments, in preference order | Process fallback |
| --- | --- | --- |
| Gemini | `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `API_KEY` | `GEMINI_API_KEY`, then `GOOGLE_API_KEY` |
| OpenAI | `OPENAI_API_KEY` only | `OPENAI_API_KEY` only |

A single pasted Google-style key is accepted in a `.env` for legacy convenience; named assignments are preferable. There is no implicit prompt. `--prompt-key` enables hidden, unsaved input only when no usable key was found, and does not bypass a malformed existing file. Console logs identify the key source, never intentionally its value. `--check-config` confirms local lookup without reading the CSV/images or sending a request; it cannot validate authentication or model access.

## Provider adapters

Gemini uses `google-genai`, explicitly selecting the Developer API (`vertexai=False`), `https://generativelanguage.googleapis.com/`, API version `v1beta`, and a millisecond timeout. Requests contain alternating image labels and JPEG bytes. The client sets SDK attempts to 1, requests plain-text output, and disables automatic function calling.

OpenAI uses `openai.OpenAI` and `responses.create` at `https://api.openai.com/v1`, with `max_retries=0`, a seconds timeout, `store=False`, text format, and inline base64 JPEGs. `openai_input` retains the common prompt/image order. `normalize_openai_response` rejects refusals/incomplete responses and excludes reasoning summaries, then adapts answer text and token usage into the Gemini-shaped validation interface.

The same domain validator is used for both. The code supports two providers, but there is not yet a clean provider-neutral request/result interface: Gemini-shaped dictionaries and completion objects remain internal coupling. Neither API adapter is an automatic fallback for the other. These fixed endpoints intentionally prevent unrelated backend/base-URL environment variables from selecting another service.

## Pacing, daily counters, and stops

Requests are sequential. `RateLimiter` spaces request starts by `60 / RPM + 0.1` seconds: 4.1 s at 15 RPM, 12.1 s at 5 RPM. A slow request naturally consumes this interval; there is no mandatory full delay after every completion. Minute pacing is per process. Run one live batch at a time for a shared allowance.

`transcribe_request_usage.json` is created beside the script, unless `--quota-file` selects another location with an existing parent directory. Keep the same counter file when moving/updating the script; otherwise the new location has no knowledge of earlier attempts. Every attempt is reserved before transmission, including retries, console/test calls, failures, and interrupted requests. Failure to persist the counter prevents a request.

Counters are keyed by `provider/model`, **not credential/project**. Multiple keys sharing a file share that local count; different files/machines do not. Counts cannot see traffic from other tools or prove the provider has remaining quota. State contains date, attempt count, and an exhausted flag, not keys/images/transcriptions. Writes use a short OS lock, flush/fsync, and atomic replacement. A damaged counter stops rather than resetting silently.

Gemini profile days use `America/Los_Angeles` (midnight with daylight-saving rules). The OpenAI profiles use UTC midnight for its local cap. No provider-side quota query occurs. Known daily exhaustion is remembered until the next local profile day; billing exhaustion is not a daily-reset diagnosis.

At a cap, `PAUSED` preserves available response text and exits with code 1 rather than waiting overnight. A normal rerun can reuse completed journal entries; a test rerun always starts fresh. Custom quota filenames and other local output paths must be kept out of Git explicitly; `.gitignore` covers the defaults.

## Retry policy

All retries use the same pacing and persistent counter. There is one total per-card attempt ceiling, with an additional limit on invalid model responses—not two independent unlimited budgets.

| Condition | Handling |
| --- | --- |
| Empty/malformed retryable response, wrong side sections, or detected LaTeX | At most one corrective retry after the first invalid response, if total attempts remain. Reuses original images and prompt plus explicit correction; does not feed the previous answer back as evidence. |
| Second invalid response | `FAILED`, retaining available text. |
| Token cutoff, safety block, refusal, or other nonretryable completion failure | `FAILED` without pretending the answer is complete; available text retained. |
| HTTP 408, 429, 500, 502, 503, 504; recognized connection/timeout errors | Retry within the total attempt limit using backoff and jitter. Exhaustion stops the batch. |
| Daily quota or billing/credit 429 | `PAUSED` immediately; daily exhaustion is persisted. |
| HTTP 400, 401, 402, 403, 404 | Fatal authentication/model/configuration failure stops the batch; no model substitution. |
| Other nonretryable per-card error | `FAILED`; subsequent cards can continue unless the error is marked fatal or raises a run-level setup/storage error. |

Backoff is the maximum of the server hint, 60 s for a retryable 429, and `min(60, retry_base * 2**(attempt-1))`, plus up to 1 s jitter bounded by `max_retry_wait`. `Retry-After` seconds/date and Google's structured `RetryInfo` are read. A requested delay above `max_retry_wait` pauses instead of shortening that delay. Format correction has zero extra backoff, but normal request pacing still applies. No sleep follows the final failed attempt.

503 is treated as service unavailability, not evidence of daily quota exhaustion. Earlier complaints that a model change “hit the rate limit after one card” motivated complete profiles and visible waits; they did not establish the precise provider-side cause of each 503.

## Usage and limits

Normal journals checkpoint per-attempt token/cost accounting and initial request provenance before readable output. Reports include the effective generation configuration, image settings, CSV-hint flag, build/prompt versions and SHA-256 fingerprints, plus the returned model version when available. Metadata contains no credentials or raw catalogue hints. Reuse preserves original provenance; unavailable legacy metadata is not reconstructed. See [report details](transcription_rules.md#reports-and-ordering) and [usage accounting](#token-usage-and-estimated-cost).

Both providers currently share a conservative estimated 19,000,000-byte inline request budget. Original JPEG bytes are retained when possible; EXIF correction or requested resizing creates in-memory bytes only. Payload limits, token-per-minute limits, account entitlement, latency, and handwriting accuracy are not guaranteed by these settings. See [testing](testing.md) and [handoff limitations](../PROJECT_HANDOFF.md#known-issues-and-technical-debt).

## Reading instructions

Reading policy and CSV-selected collector instructions are configured in [egg_slip_prompt.py](../egg_slip_prompt.py), separately from provider settings. See [prompt customization](transcription_rules.md#editing-the-prompt-and-collector-guidance). `--no-csv-hints` disables both catalogue hints and collector-specific guidance.


## Token usage and estimated cost

`token_usage.py` centralizes normalized usage, aggregation, and `PRICES`, a table of standard paid USD rates per million tokens (input, cached input, output including reasoning). No network lookup or extra token-counting API call occurs during transcription. Rates were checked on 23 September 2026 against [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing), [OpenAI pricing](https://developers.openai.com/api/docs/pricing), and the official [Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna), [Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra), and [Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol) model pages.

All configured models have estimates. Gemini 3.6/3.8 rates follow the published increase on 1 January 2027. GPT-5.6 Sol estimates become unknown after 21 November 2026 until its promotional pricing is reviewed. OpenAI requests above 272,000 input tokens use the published long-context multipliers. Reported cached-input tokens receive the discounted input rate; reasoning is billed once as output. Prices and accounting metadata do not affect transcription cache fingerprints.

Amounts are estimates at standard paid rates, not invoices. Free-tier access, account credits/discounts, tax, regional/priority processing, explicit cache-write/storage charges, and future pricing changes are not inferred from token usage. This application does not request tools, explicit context-cache storage, or a special service tier. Review `PRICES` when pricing changes or adding a model; an unknown model's cost is shown as unknown while tokens still count. The rate table is deliberately independent of request profiles and never changes the requested model.

Every attempted API call counts, including service errors, rejected output and interrupted requests. Responses are measured before validation. A call without returned usage has unknown cost rather than a presumed zero. Quota persistence and pacing still count attempts independently. Report footers describe this invocation; they are not an account-wide billing ledger. See [report conventions](transcription_rules.md#reports-and-ordering).
