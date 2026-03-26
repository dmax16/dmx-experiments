"""TrackedAnthropic — drop-in replacement for anthropic.Anthropic.

Wraps the Anthropic client to intercept messages.create() calls and log
token usage to Supabase. All other attributes are delegated transparently.
"""

from anthropic import Anthropic
from anthropic.types import Message

from dmax_token_tracker.tracker import log_usage


class _TrackedMessages:
    """Wraps client.messages to intercept create() calls."""

    def __init__(self, messages) -> None:
        self._messages = messages

    def create(self, **kwargs) -> Message:
        response = self._messages.create(**kwargs)
        log_usage(response)
        return response


class TrackedAnthropic:
    """Drop-in replacement for anthropic.Anthropic with usage logging.

    Intercepts messages.create() to log token usage and cost to Supabase.
    All other attribute access is delegated to the underlying Anthropic client.
    """

    def __init__(self, **kwargs) -> None:
        self._client = Anthropic(**kwargs)
        self.messages = _TrackedMessages(self._client.messages)

    def __getattr__(self, name: str):
        return getattr(self._client, name)
