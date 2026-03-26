# PROJECT.md — DMX Experiments Catalogue

_Last updated: 2026-03-26 (decisions finalised)_

---

## Problem Statement

dmax builds AI tools and prototypes regularly. Right now there is no central
place to browse them, search them, or share a link with a colleague. This site
solves that: a personal lab notebook, always at the same URL, that catalogues
every experiment with enough context to know what it is and whether it still
works.

---

## Audience

- **dmax** — primary user, browses and shares
- **Colleagues** — receive links, need zero setup, just open a URL

---

## Feature List

### Index page (`index.html`)

| Feature | Description |
|---------|-------------|
| Cards grid | One card per experiment, rendered from `experiments.json` |
| Live search | Filters cards as you type. Matches title, description, tags, and stack. |
| Tag filter pills | Multi-select. Click any tag to activate it; click again to deactivate. Multiple tags can be active at once. Logic: OR — shows experiments matching ANY active tag. |
| Status filter | Row of toggles: All / Working / Broken / Archived. Sits near tag pills, visually distinct. Default: All. |
| Sort control | Two options: "Newest first" / "Oldest first" (by `date` field). Default: Newest first. |
| Status badge | Each card shows `working`, `broken`, or `archived` with colour coding |
| Tag icon | When no screenshot exists, a relevant icon (mapped from `tags[0]`) fills the thumbnail area |
| Empty state | Friendly message when search + filter produce no results |
| Card click | Clicking anywhere on a card opens the experiment URL |

### Per-experiment pages

Each experiment is a self-contained HTML file. The catalogue links to it.
No shared layout or shared JS between experiments — each is fully independent.

---

## Data Model

File: `experiments.json` — an array of experiment objects.

```json
{
  "id": "string — unique, kebab-case, matches filename (e.g. 'concerts-dashboard')",
  "title": "string",
  "description": "string — 1-2 sentences: what it does and why it's interesting",
  "url": "string — relative path to the experiment file",
  "date": "string — YYYY-MM format",
  "status": "working | broken | archived",
  "tags": ["array of lowercase strings — tags[0] is the primary category"],
  "stack": ["array of strings — tools/tech used, e.g. 'Claude AI', 'HTML'"],
  "thumbnail": "string | null — relative path to screenshot, or null for auto-icon"
}
```

**Tag order matters.** `tags[0]` is the primary category and drives the
auto-generated icon when `thumbnail` is null.

---

## Visual Style

**Reference:** `concerts-dashboard.html` sets the visual vocabulary.

| Token | Value | Usage |
|-------|-------|-------|
| Background | `#0f0f13` | Page background |
| Surface | `#1a1a2e` | Cards, header |
| Border | `#ffffff12` | Card borders |
| Text primary | `#e8e8f0` | Headings, body |
| Text muted | `#94a3b8` | Descriptions, dates |
| Text faint | `#64748b` | Labels, metadata |
| Accent violet | `#a78bfa` | Highlights, active states |
| Status green | `#4ade80` | `working` badge |
| Status red | `#f87171` | `broken` badge |
| Status gray | `#64748b` | `archived` badge |
| Border radius | `12px` | Cards |
| Font | `-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif` | All text |

**Tone:** Personal and playful, not corporate. Lab notebook, not portfolio.
Minimal chrome — the experiments are the content.

---

## Tag → Icon Map

When `thumbnail` is null, `tags[0]` maps to a display character shown in the
card's visual area. These are Unicode emoji — no external dependencies.

| Tag | Icon |
|-----|------|
| `data viz` | 📊 |
| `automation` | ⚙️ |
| `ai` | 🤖 |
| `dashboard` | 🗂️ |
| `chat` | 💬 |
| `writing` | ✍️ |
| `code` | 💻 |
| `search` | 🔍 |
| `image` | 🖼️ |
| `audio` | 🎵 |
| `utility` | 🔧 |
| _(default)_ | 🧪 |

dmax can extend this map by editing `index.html`. New tags not in the map fall
back to 🧪.

---

## File Structure

```
/
├── index.html              # Catalogue — search, filter, cards grid
├── experiments.json        # Data file — one entry per experiment
├── CLAUDE.md               # CTO instructions
├── PROJECT.md              # This file
├── concerts-dashboard.html # First experiment
└── [future experiments]/   # Each experiment as its own file(s)
```

No subdirectories for assets at this stage. Screenshots (when added) live at
the repo root alongside the experiment they belong to, named
`[id]-thumb.png`.

---

## Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Theme | Dark (matches `concerts-dashboard.html`) | Visual consistency when navigating between pages |
| Data loading | `fetch('experiments.json')` | Keeps data in `.json` as requested; works on GitHub Pages |
| Local file:// testing | Requires a local server | `fetch()` blocked by Chrome on `file://`; `python3 -m http.server` or VS Code Live Server solves this |
| Tag filter | Multi-select, OR logic | Multiple active tags show experiments matching any of them — broader is more useful for browsing |
| Status filter | All / Working / Broken / Archived toggles | Quick way to surface only live experiments or browse archived ones |
| Sort control | Newest first (default) / Oldest first | By `date` field; two options only, no over-engineering |
| Search scope | Title + description + tags + stack | Broad enough to be useful without needing an index |
| Card click target | Entire card | Better UX than a small button |
| Thumbnail fallback | Tag icon (emoji) | No external deps; always renders; primary tag drives the icon |
| No screenshot automation | Manual `thumbnail` field in JSON | Static site constraint — no build step to generate screenshots |

---

## What This Is NOT

- Not a CMS. dmax edits `experiments.json` by hand.
- Not a build system. No npm, no Webpack, no bundler.
- Not a backend. No server, no database, no API.
- Not a framework. Vanilla HTML, CSS, JavaScript only.
