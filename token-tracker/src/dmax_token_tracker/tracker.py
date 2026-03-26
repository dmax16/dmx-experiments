"""Supabase logging logic.

Extracts usage data from Anthropic API responses and writes rows to the
api_calls table. All operations are non-fatal: logging failures are written
to stderr but never prevent the API response from reaching the caller.
"""

import os
import sys

from dmax_token_tracker.pricing import get_pricing

_supabase_client = None
_logging_disabled: bool = False


def _get_client():
    """Lazy-initialize the Supabase client on first call.

    If credentials are missing or client creation fails, disables all future
    logging attempts to avoid repeated timeouts.
    """
    global _supabase_client, _logging_disabled

    if _supabase_client is not None:
        return _supabase_client

    if _logging_disabled:
        return None

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        _logging_disabled = True
        print(
            "\n[dmax-token-tracker] WARNING: SUPABASE_URL and/or SUPABASE_KEY not set. "
            "Token usage logging is DISABLED for this session.\n",
            file=sys.stderr,
        )
        return None

    try:
        from supabase import create_client
        from supabase import ClientOptions

        _supabase_client = create_client(
            url,
            key,
            options=ClientOptions(postgrest_client_timeout=5),
        )
        return _supabase_client
    except Exception as e:
        _logging_disabled = True
        print(
            f"\n[dmax-token-tracker] WARNING: Failed to initialize Supabase client: {e}. "
            "Token usage logging is DISABLED for this session.\n",
            file=sys.stderr,
        )
        return None


def log_usage(response) -> None:
    """Extract usage from an Anthropic response and insert a row into Supabase.

    Non-fatal: any exception is caught and logged to stderr.
    """
    if _logging_disabled:
        return

    try:
        client = _get_client()
        if client is None:
            return

        usage = response.usage
        input_tokens: int = usage.input_tokens
        output_tokens: int = usage.output_tokens
        model: str = response.model

        # Cache tokens — may be None or absent
        cache_creation = getattr(usage, "cache_creation_input_tokens", None) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", None) or 0

        # Cost calculation
        pricing = get_pricing(model)
        if pricing is not None:
            cost_usd = (
                input_tokens * pricing["input"]
                + output_tokens * pricing["output"]
                + cache_creation * pricing["cache_write"]
                + cache_read * pricing["cache_read"]
            )
        else:
            cost_usd = 0.0
            print(
                f"[dmax-token-tracker] WARNING: No pricing found for model '{model}'. "
                "cost_usd set to 0.0.",
                file=sys.stderr,
            )

        project = os.getenv("PROJECT_NAME", "unknown")

        # Build metadata — only include cache fields if non-zero
        metadata: dict | None = None
        if cache_creation or cache_read:
            metadata = {}
            if cache_creation:
                metadata["cache_creation_input_tokens"] = cache_creation
            if cache_read:
                metadata["cache_read_input_tokens"] = cache_read

        row = {
            "project": project,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": float(cost_usd),
            "metadata": metadata,
        }

        client.table("api_calls").insert(row).execute()

    except Exception as e:
        print(f"[dmax-token-tracker] Logging failed: {e}", file=sys.stderr)
