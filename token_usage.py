"""Provider usage and paid-rate estimates; no document-domain assumptions."""
from datetime import datetime, timezone

# Standard USD / million tokens: input, cached input, output including reasoning.
# Verified 2026-09-23: https://ai.google.dev/gemini-api/docs/pricing
# https://developers.openai.com/api/docs/pricing and /models/gpt-5.6-{luna,terra,sol}
PRICES = {
    "gemini-3.5-flash-lite": (0.30, 0.03, 2.50),
    "gemini-3.6-flash": (0.75, 0.075, 3.75),
    "gemini-3.8-flash": (0.75, 0.075, 3.75),
    "gpt-5.6-luna": (0.20, 0.02, 1.20),
    "gpt-5.6-terra": (2.00, 0.20, 12.00),
    "gpt-5.6-sol": (4.00, 0.40, 20.00),
    "gpt-6-astra": (10.00, 1.00, 50.00),
}
FIELDS = ("input", "output", "reasoning", "total")


def count(obj, name, default=None):
    value = getattr(obj, name, default)
    return value if type(value) is int and value >= 0 else default


def read_usage(response, provider):
    """Output excludes reasoning for BOTH providers; billed_output includes it."""
    if provider == "openai":
        obj = getattr(response, "usage", None)
        reasoning = count(getattr(obj, "output_tokens_details", None), "reasoning_tokens", 0)
        billed = count(obj, "output_tokens")
        return dict(input=count(obj, "input_tokens"),
                    output=max(0, billed - reasoning) if billed is not None else None,
                    reasoning=reasoning if obj is not None else None,
                    total=count(obj, "total_tokens"), billed_output=billed,
                    cached=count(getattr(obj, "input_tokens_details", None), "cached_tokens", 0))
    obj = getattr(response, "usage_metadata", None)
    output = count(obj, "candidates_token_count")
    reasoning = count(obj, "thoughts_token_count", 0) if obj is not None else None
    return dict(input=count(obj, "prompt_token_count"), output=output,
                reasoning=reasoning, total=count(obj, "total_token_count"),
                billed_output=output + reasoning if output is not None else None,
                cached=count(obj, "cached_content_token_count", 0))


def estimate(usage, model, today=None):
    today = today or datetime.now(timezone.utc).date()
    rates = PRICES.get(model)
    if rates is None or usage["input"] is None or usage["billed_output"] is None:
        return None
    if model == "gpt-5.6-sol" and today.isoformat() > "2026-11-21":
        return None  # Promotion has no guaranteed price after this date.
    inp, cached, out = rates
    if model in {"gemini-3.6-flash", "gemini-3.8-flash"} and today.year >= 2027:
        inp, cached, out = inp * 2, cached * 2, out * 2
    if model.startswith("gpt-") and usage["input"] > 272_000:
        inp, cached, out = inp * 2, cached * 2, out * 1.5
    cache_tokens = min(usage["cached"], usage["input"])
    return ((usage["input"] - cache_tokens) * inp + cache_tokens * cached
            + usage["billed_output"] * out) / 1_000_000


def tokens_line(usage):
    def number(key):
        value = usage.get(key)
        return "unknown" if value is None else f"{value:,}"
    return "TOKENS: " + " | ".join(f"{number(key)} {label}" for key, label in
                                    zip(FIELDS, ("in", "out", "think", "total")))


def aggregate(calls):
    return {key: (sum(call["usage"][key] for call in calls)
                  if all(call["usage"].get(key) is not None for call in calls) else None)
            for key in FIELDS}


def cost_text(calls, digits=4):
    known = [call["cost_usd"] for call in calls if call.get("cost_usd") is not None]
    if len(known) == len(calls):
        return f"${sum(known):.{digits}f}"
    subtotal = f"${sum(known):.{digits}f} known + " if known else ""
    return subtotal + f"unknown ({len(calls) - len(known)} call(s))"


def summary(calls):
    usage = aggregate(calls)
    total = (f"{usage['total']:,}" if usage["total"] is not None else
             f"{sum(call['usage'].get('total') or 0 for call in calls):,} known")
    return f"RUN: {len(calls):,} calls | {total} tokens | {cost_text(calls, 2)}"


def averages(calls):
    complete = [call for call in calls if all(call["usage"].get(key) is not None for key in FIELDS)]
    if not complete:
        return "AVERAGE/CALL: unavailable (no calls with complete usage)"
    totals = aggregate(complete)
    values = {key: round(totals[key] / len(complete)) for key in FIELDS}
    return (f"AVERAGE/CALL ({len(complete)}/{len(calls)} calls with complete usage): "
            + tokens_line(values).removeprefix("TOKENS: "))
