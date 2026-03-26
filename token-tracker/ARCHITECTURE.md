# ARCHITECTURE.md — dmax Token Tracker

_Last updated: 2026-03-26_

This is the authoritative technical reference for the token tracker system.
All agents working on this project must read this document before doing any
work.

---

## System Overview

```
Project code
    │
    │  from dmax_token_tracker import TrackedAnthropic
    │  client = TrackedAnthropic()
    ▼
TrackedAnthropic (wrapper)
    │
    ├─── forwards call to real Anthropic client
    │         │
    │         ▼
    │    Anthropic API (response includes usage)
    │         │
    │    response returned to wrapper
    │
    ├─── extracts: input_tokens, output_tokens, model
    ├─── calculates: cost_usd (from pricing.py)
    ├─── reads: PROJECT_NAME from env
    │
    ▼
Supabase insert (non-fatal)
    │
    ├─── success → row written to api_calls table
    └─── failure → log to stderr, return response unchanged

Response returned to caller (unchanged)
```

---

## Package Structure

```
token-tracker/
├── CLAUDE.md
├── PROJECT.md
├── ARCHITECTURE.md
├── pyproject.toml              # Package metadata, dependencies
├── .env.example                # Template for required env vars
└── src/
    └── dmax_token_tracker/
        ├── __init__.py         # Exports TrackedAnthropic
        ├── client.py           # TrackedAnthropic wrapper class
        ├── tracker.py          # Supabase logging logic
        └── pricing.py          # Model pricing config dict
```

The package lives inside the `dmx-experiments` repo under `token-tracker/`.
Other projects install it with:

```bash
pip install -e /path/to/dmx-experiments/token-tracker
```

---

## Wrapper Design

### `TrackedAnthropic` (client.py)

The wrapper is a class that:
- Accepts the same constructor arguments as `anthropic.Anthropic`
- Internally instantiates a real `Anthropic` client
- Exposes a `messages` attribute that is a `_TrackedMessages` object
- Delegates all other attribute access to `self._client` via `__getattr__`,
  so projects that access `client.api_key`, `client.models`, etc. continue
  to work without changes

```python
class TrackedAnthropic:
    def __init__(self, **kwargs):
        self._client = Anthropic(**kwargs)
        self.messages = _TrackedMessages(self._client.messages)

    def __getattr__(self, name: str):
        return getattr(self._client, name)
```

### `_TrackedMessages`

Wraps `client.messages` and intercepts `create()`:

```python
class _TrackedMessages:
    def __init__(self, messages):
        self._messages = messages

    def create(self, **kwargs):
        response = self._messages.create(**kwargs)
        log_usage(response)
        return response
```

`log_usage` uses `response.model` as the model name (always present on a
successful response, and reflects what the API actually used). It is
non-fatal: any exception is caught, written to stderr, and the response is
returned unchanged.

### Design rationale

- **Wrap the client, not individual methods.** Projects call
  `client.messages.create()`. The wrapper intercepts at that level without
  touching the underlying SDK.
- **Transparent to callers.** The response object returned is the real
  Anthropic response — not a copy, not a wrapper. Callers can access any
  field they expect.
- **No monkey-patching.** The wrapper is explicit: you get `TrackedAnthropic`
  when you import it. There is no global patching of the `anthropic` module.

### Phase 1 scope

Phase 1 wraps **synchronous `messages.create()` only**.

Not in scope for Phase 1:
- `messages.stream()` — Phase 2
- `AsyncAnthropic` — Phase 2
- `messages.count_tokens()` — no usage to log
- The legacy `completions` API — no target project uses it

---

## Tracker Module (tracker.py)

Responsible for extracting usage data and writing to Supabase.

### Usage extraction

The Anthropic SDK returns usage in `response.usage`:

| Field | Type | Notes |
|-------|------|-------|
| `input_tokens` | int | Always present |
| `output_tokens` | int | Always present |
| `cache_creation_input_tokens` | int \| None | Present when prompt caching is active |
| `cache_read_input_tokens` | int \| None | Present when prompt caching is active |

### Cost calculation

```
cost = (input_tokens × input_price_per_token)
     + (output_tokens × output_price_per_token)
     + (cache_creation_input_tokens × cache_write_price_per_token)   [if present]
     + (cache_read_input_tokens × cache_read_price_per_token)        [if present]
```

Prices come from `pricing.py`. If the model is not in the pricing dict, cost
is set to `0.0` and a warning is written to stderr.

Cache token counts, if present, are also stored in `metadata` for
auditability.

### Supabase client initialization

The Supabase client is initialized **lazily** — on the first call, not at
import time. This means importing `dmax_token_tracker` never fails due to
missing env vars.

On first-call init failure (missing credentials, bad URL, etc.), a prominent
warning is printed to stderr and a module-level flag is set to disable all
further Supabase attempts for the session. This avoids repeated connection
timeouts (which could add several seconds of latency to every API call).

The Supabase client is initialized with a **5-second timeout** to prevent
network hangs from blocking API call returns.

Required env vars for Supabase:
- `SUPABASE_URL`
- `SUPABASE_KEY` — must be the **service_role** key (bypasses RLS, allows
  INSERT). The anon key is read-only and will fail on every insert.

### Non-fatal contract

The tracker MUST NOT allow a logging failure to break the API call.

Pattern:
```python
try:
    _insert_row(row_data)
except Exception as e:
    print(f"[dmax-token-tracker] Logging failed: {e}", file=sys.stderr)
```

The API response is always returned to the caller.

---

## Pricing Config (pricing.py)

A plain Python dict mapping model base name prefixes to per-token prices in USD.

### Prefix matching

The Anthropic API returns **versioned** model IDs in `response.model` (e.g.
`claude-opus-4-6-20250514`), not the base name the caller passed. The pricing
lookup uses prefix matching: iterate PRICING keys, find the first key where
`response.model.startswith(key)`, use that entry's prices. If no prefix
matches, cost is set to `0.0` and a warning is written to stderr.

This means new versioned releases of a model are priced automatically without
requiring a pricing dict update.

```python
PRICING = {
    "claude-opus-4-6": {
        "input":         15.00 / 1_000_000,
        "output":        75.00 / 1_000_000,
        "cache_write":   18.75 / 1_000_000,   # 1.25× input
        "cache_read":     1.50 / 1_000_000,   # 0.10× input
    },
    "claude-sonnet-4-6": {
        "input":          3.00 / 1_000_000,
        "output":        15.00 / 1_000_000,
        "cache_write":    3.75 / 1_000_000,
        "cache_read":     0.30 / 1_000_000,
    },
    "claude-haiku-4-5": {
        "input":          0.80 / 1_000_000,
        "output":          4.00 / 1_000_000,
        "cache_write":    1.00 / 1_000_000,
        "cache_read":     0.08 / 1_000_000,
    },
    # Add new model families here when Anthropic releases them
}
```

**Maintenance note:** This dict must be kept in sync with Anthropic's actual
published pricing. When pricing changes, a human updates this file. The CTO
must surface pricing discrepancies to dmax before implementation if any are
found.

**Important:** Prices above are based on Anthropic's pricing as of August
2025 (knowledge cutoff). Verify against https://www.anthropic.com/pricing
before Phase 1 implementation and update if anything has changed.

---

## Supabase Schema

This project uses a **dedicated Supabase project** — not the one used by
Comms Hub or any other dmax project.

```sql
CREATE TABLE api_calls (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at    timestamptz NOT NULL DEFAULT now(),
  project       text        NOT NULL DEFAULT 'unknown',
  model         text        NOT NULL,
  input_tokens  integer     NOT NULL,
  output_tokens integer     NOT NULL,
  cost_usd      numeric(10, 6) NOT NULL,
  metadata      jsonb
);
```

### Column notes

| Column | Notes |
|--------|-------|
| `project` | Value of `PROJECT_NAME` env var. Defaults to `"unknown"` — never NULL, never dropped |
| `model` | Full model ID string as returned by the API (e.g. `"claude-opus-4-6"`) |
| `input_tokens` | From `response.usage.input_tokens` |
| `output_tokens` | From `response.usage.output_tokens` |
| `cost_usd` | Calculated from pricing.py. `0.0` if model not in pricing dict |
| `metadata` | JSON blob. Phase 1: stores `cache_creation_input_tokens` and `cache_read_input_tokens` if present |

### Recommended indexes (add after schema creation)

```sql
CREATE INDEX ON api_calls (project);
CREATE INDEX ON api_calls (created_at);
```

---

## Environment Variables

Each project using the wrapper needs these in its `.env`:

```
# Required: identifies which project made the calls
PROJECT_NAME=comms-hub

# Required: Supabase connection — use the service_role key, NOT the anon key.
# The anon key is read-only; the service_role key bypasses RLS and allows INSERT.
# Find it in: Supabase dashboard → Settings → API → service_role key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=eyJ...your-service-role-key...
```

Template file: `.env.example` (in this package)

The wrapper reads these env vars at call time (not at import time), so it
picks up values from the calling project's environment. Do NOT call
`load_dotenv()` inside the wrapper — the calling project is responsible for
loading its own `.env`.

---

## How Other Projects Adopt the Wrapper

### 1. Install the package

```bash
pip install -e /path/to/dmx-experiments/token-tracker
```

Or add to `requirements.txt`:
```
dmax-token-tracker @ file:///path/to/dmx-experiments/token-tracker
```

### 2. Add env vars to `.env`

```
PROJECT_NAME=your-project-name
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
```

### 3. Change one import line

```python
# Before
from anthropic import Anthropic
client = Anthropic()

# After
from dmax_token_tracker import TrackedAnthropic
client = TrackedAnthropic()
```

No other changes required. All existing `client.messages.create()` calls
work identically.

### Validation checklist (before any project adopts the wrapper)

- [ ] Make a test `messages.create()` call through the wrapper
- [ ] Confirm a row appears in Supabase with correct token counts
- [ ] Verify cost calculation: `(input × input_price) + (output × output_price)`
- [ ] Confirm `project` column matches `PROJECT_NAME` env var
- [ ] Test with `SUPABASE_URL` unset: API call succeeds, stderr has warning
- [ ] Test with `PROJECT_NAME` unset: API call succeeds, row has `project = "unknown"`

**Comms Hub:** Not on the development machine as of 2026-03-26. Must be
validated against this checklist before Comms Hub adopts the wrapper.
Validation is a Phase 1 task, not a pre-condition for building the wrapper.

---

## Dashboard Integration (Phase 4)

The dashboard is a static HTML file in the `dmx-experiments` repo
(e.g. `token-tracker-dashboard.html`). It reads from this Supabase project
via the Supabase JS client loaded from CDN. It does not write to Supabase.

It will be built through the standard agent workflow — no Lovable involved.
The Supabase anon key will be present in client-side JS, which is acceptable
for a read-only dataset.

---

## Lovable Prompt (for Supabase setup only)

Use this prompt in Lovable (or directly in the Supabase dashboard) to create
the project and schema. The dashboard itself will be built as a static HTML
file — Lovable is not needed for that.

```
I need to set up a new Supabase project for a token usage tracker.

Create a new Supabase project called "dmax-token-tracker".

Run this SQL to create the schema:

CREATE TABLE api_calls (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at    timestamptz NOT NULL DEFAULT now(),
  project       text        NOT NULL DEFAULT 'unknown',
  model         text        NOT NULL,
  input_tokens  integer     NOT NULL,
  output_tokens integer     NOT NULL,
  cost_usd      numeric(10, 6) NOT NULL,
  metadata      jsonb
);

CREATE INDEX ON api_calls (project);
CREATE INDEX ON api_calls (created_at);

Enable Row Level Security and add a policy that allows SELECT for the anon
role. The anon key should be read-only — no INSERT, UPDATE, or DELETE for
anon.

Once done, give me the project URL and anon key.
```

---

## Known Gaps and Non-Issues

| Gap | Status |
|-----|--------|
| Claude Code sub-agent calls cannot be intercepted | Accepted. Track separately in Anthropic dashboard. |
| Streaming responses not logged in Phase 1 | Deferred to Phase 2 |
| AsyncAnthropic not wrapped in Phase 1 | Deferred to Phase 2 |
| Pricing dict requires manual maintenance | Accepted. Human updates pricing.py when Anthropic changes prices. |
| Supabase anon key visible in client-side dashboard JS | Acceptable for read-only data. Not a secret that needs protecting. |
| End-to-end live API test not yet run | **Pending.** ANTHROPIC_API_KEY was unavailable during Phase 1 build. Supabase connection, insert path, pricing logic, resilience, and project tagging were all verified with mock responses. Live interception of a real `messages.create()` call must be validated before Comms Hub adopts the wrapper. See manual test command below. |

## Manual End-to-End Test

Run this once you have your Anthropic API key. Replace the two placeholders:
- `sk-ant-...` — your Anthropic API key
- `YOUR_SUPABASE_SERVICE_ROLE_KEY` — Supabase dashboard → Settings → API → service_role

```bash
ANTHROPIC_API_KEY=sk-ant-... \
SUPABASE_URL=https://wtarccxwnfpbptzolxht.supabase.co \
SUPABASE_KEY=YOUR_SUPABASE_SERVICE_ROLE_KEY \
PROJECT_NAME=token-tracker-test \
python3 -c "
from dmax_token_tracker import TrackedAnthropic
client = TrackedAnthropic()
r = client.messages.create(
    model='claude-haiku-4-5-20251001',
    max_tokens=10,
    messages=[{'role': 'user', 'content': 'Say: test'}]
)
print(f'OK — {r.usage.input_tokens} in / {r.usage.output_tokens} out / model: {r.model}')
print('Check Supabase api_calls table for the new row.')
"
```

**What to verify in Supabase afterward:**
- A new row exists in `api_calls`
- `project` = `"token-tracker-test"`
- `model` matches what printed above
- `cost_usd` = `(input_tokens × 0.0000008) + (output_tokens × 0.000004)`
- `metadata` is null (no cache tokens in this call)
