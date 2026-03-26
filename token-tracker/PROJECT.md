# PROJECT.md — dmax Token Tracker

_Last updated: 2026-03-26_

---

## Problem Statement

dmax runs multiple AI projects that make Anthropic API calls. Right now there
is no visibility into what each project costs, how usage trends over time, or
which models are consuming the most tokens. Bills arrive from Anthropic with
no per-project breakdown.

This project solves that: a lightweight Python package that intercepts
Anthropic SDK calls, logs usage and cost to a database, and exposes the data
through a dashboard on the dmx-experiments website.

---

## Goals

1. **Per-project cost visibility.** Every API call is tagged with the project
   that made it. Costs are aggregated by project, by model, and over time.

2. **Zero friction adoption.** Any project that uses the Anthropic SDK can
   adopt the tracker by changing one import line. No changes to how the API
   is called.

3. **Accurate cost data.** Token counts and costs are derived from the actual
   API response — not estimated. This data should be trustworthy enough to
   use for billing decisions.

4. **Non-fatal logging.** If the tracker fails (Supabase is down, env vars
   are missing), the API call still succeeds. Logging failure is a monitoring
   problem, not an application problem.

---

## Scope

### Phase 1 — Core wrapper (build this first)

- Python package `dmax-token-tracker`, installable via pip
- `TrackedAnthropic` class: drop-in replacement for `anthropic.Anthropic`
- Intercepts synchronous `messages.create()` calls
- Logs to Supabase: project, model, input_tokens, output_tokens, cost_usd
- Cache token fields (if present) stored in `metadata`, priced accurately
- Project tagging via `PROJECT_NAME` env var
- Pricing config dict for known models (human-maintained)

### Phase 2 — Streaming and async support

- Intercept `messages.stream()` calls
- Usage data is only available in the final chunk of a stream — the wrapper
  must buffer and extract it
- `TrackedAsyncAnthropic` for projects using the async Anthropic client
  (deferred from Phase 1 — no current target project uses it)

### Phase 3 — GCP cost tracking

- Separate integration to pull Google Cloud billing data into the same
  database
- Scope and design TBD

### Phase 4 — Dashboard

- New section on the dmx-experiments website showing token usage and cost
- Reads from the token tracker Supabase project (read-only)
- Per-project breakdown, model breakdown, time series

---

## Out of Scope

- Tracking API calls made by Claude Code's internal sub-agents. These cannot
  be intercepted by the Python wrapper. They are visible in Anthropic's usage
  dashboard. This is a known gap, not a bug.
- The older `completions` API. All target projects use `messages`.
- Modifying how any project calls the API. The wrapper is transparent.

---

## Known Limitations

- **The sub-agent gap.** Claude Code's sub-agents make direct API calls that
  the wrapper cannot see. Accepted and documented.
- **Pricing dict maintenance.** When Anthropic changes pricing, a human must
  update `pricing.py`. There is no automatic sync.
- **Streaming (Phase 1).** Streaming calls are not intercepted in Phase 1.
  If a project uses streaming, those calls will not be logged until Phase 2.
- **Async (Phase 1).** `AsyncAnthropic` is not wrapped in Phase 1. Deferred
  to Phase 2. No current target project uses it.

---

## Success Criteria

Phase 1 is done when:

- A project can adopt the wrapper by changing one import line and setting
  `PROJECT_NAME` in its `.env`
- Every `messages.create()` call lands a row in Supabase with correct token
  counts and cost
- If Supabase is unreachable, the API call still succeeds and the failure is
  logged to stderr
- Comms Hub has been validated against the wrapper before it adopts it

---

## Projects That Will Use This

| Project | Notes |
|---------|-------|
| Comms Hub | First planned adopter. Not on this machine — validate before adoption. |
| peterbot | No Anthropic SDK usage found in codebase (as of 2026-03-26). Likely not a current target. |
| Future projects | All new dmax projects should add the wrapper from day one |
