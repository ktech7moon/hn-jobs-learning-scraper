"""Per-model pricing for cost calculations.

Rates are USD per million tokens, captured from
https://www.anthropic.com/pricing as of 2026-05. If Anthropic
changes pricing, edit this table. The cost number that lands in
the Markdown digest is approximate by design — a published list
price applied to logged token counts. Real billing comes from
Anthropic's invoice, not from us.
"""

from __future__ import annotations

# (input_per_mtok, output_per_mtok)
RATES_USD: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-7": (15.00, 75.00),
}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return the published-rate cost in USD for one call.

    Falls back to ``0.0`` for unknown models so a missing rate row
    doesn't crash the digest. Surface the gap by checking
    :func:`is_priced` if you need certainty.
    """
    rate = RATES_USD.get(model)
    if rate is None:
        return 0.0
    in_rate, out_rate = rate
    return (input_tokens / 1_000_000) * in_rate + (output_tokens / 1_000_000) * out_rate


def is_priced(model: str) -> bool:
    return model in RATES_USD
