"""Model pricing configuration.

Maps model name prefixes to per-token prices in USD. The Anthropic API returns
versioned model IDs (e.g. "claude-opus-4-6-20250514"), so lookup uses prefix
matching: the first key where response.model.startswith(key) wins.

Prices must be kept in sync with https://www.anthropic.com/pricing manually.
"""

PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-6": {
        "input":        15.00 / 1_000_000,
        "output":       75.00 / 1_000_000,
        "cache_write":  18.75 / 1_000_000,
        "cache_read":    1.50 / 1_000_000,
    },
    "claude-sonnet-4-6": {
        "input":         3.00 / 1_000_000,
        "output":       15.00 / 1_000_000,
        "cache_write":   3.75 / 1_000_000,
        "cache_read":    0.30 / 1_000_000,
    },
    "claude-haiku-4-5": {
        "input":         0.80 / 1_000_000,
        "output":        4.00 / 1_000_000,
        "cache_write":   1.00 / 1_000_000,
        "cache_read":    0.08 / 1_000_000,
    },
    # Add new model families here when Anthropic releases them
}


def get_pricing(model: str) -> dict[str, float] | None:
    """Return the pricing entry for a model using prefix matching.

    Returns None if no prefix in PRICING matches the given model string.
    """
    # Dict iteration order matters: more specific prefixes must come first for overlapping matches.
    for prefix, prices in PRICING.items():
        if model.startswith(prefix):
            return prices
    return None
