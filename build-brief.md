# Build Brief — TCS Internal Dashboard (for Claude Code)

You are building the **front-end** for an internal company health + priorities dashboard. The data
pipeline (Hermes) already produces a real `data.json` — you build the static site that renders it.
**Do not build a backend, do not invent data, do not hardcode metrics.** Read `data-contract.md`
for the exact schema and `metric-definitions.md` for the meaning of each field.

## What this is

A **triage board**, not an analytics tool. Every element answers "is this OK, and if not, what's
the action?" The user (Andrew + his marketing/ops team) opens it to see **what needs help, what's
wrong, and what to work on** — without Andrew narrating it each morning.

## Tech constraints (LOCKED)

- **Static site** — HTML/CSS/vanilla JS (or a light framework if you prefer, but static output).
  No server. It must build to plain static files.
- Reads **`data.json`** at the site root (fetch on load). Handle the file being briefly absent
  (show a "refreshing…" state, not an error).
- **Hosting: GitHub Pages** behind **one shared team password** (basic-auth style gate — a simple
  client-side password prompt is acceptable for v1; it's obscure-URL + shared-password, internal
  only). No per-user logins.
- **Auto-refresh:** re-fetch `data.json` every ~5 min (the pipeline updates it hourly; retainers daily).
- **Responsive** but **desktop-first** (the team views on desktop; mobile should not break).

## Brand (LOCKED — see references/brand-kit.md)

- **Theme: dark background with light/white tables & cards.** Low-medium whitespace.
- Logo: white-text-on-transparent (dark-ready) — provided at `templates/assets/logo.png`.
- Primary accent: cyan/teal (`#32e6e2` / `#6CFFF3` / `#71F9F9`). Text: white with subtle cyan tint.
- Status colors: green `#30a46c`, amber `#f5a524`, red `#e5484d`.
- **An approved visual mockup exists at `templates/dashboard-mockup.html` — match its look.** It is
  the source of truth for layout, spacing, and component styling. Use it as the starting HTML/CSS.

## Layout (LOCKED — top to bottom)

1. **Header** — logo left; right side shows `data_freshness` ("Data as of …") + any
   `stale_warnings` as a warning chip.
2. **Top row (side by side):**
   - **"Needs Attention"** card — renders `needs_attention[]`, red first then amber. Each row:
     level pill, tort/buyer name, `reason`, and `owner` (→ owner).
   - **"Andrew's Tort Priorities"** card — renders `andrew_priorities[]` as a numbered list, plus
     `andrew_note` as a highlighted quote callout below it.
3. **Company KPI strip** — renders `company`: spend, revenue, gross profit, margin %, cost/sign,
   payable leads. (NO CPL here — CPL is never a headline.)
4. **Torts board — a dense TABLE.** Columns: Status pill · Tort · Spend · Revenue · Margin %
   (color-coded) · CPL · Cost/Sign · Leads · Signs · Note (Andrew's per-row comment, prefixed
   "Andrew:" when `note_author` is Andrew). Sorted by spend desc. If `data_ok==false`, render the
   row in an amber ⚠️ state, not real numbers. If `spend_caveat` set, show it (small, under spend).
5. **Buyers board — CARDS (5).** Each card: buyer name + status pill (top border color = status),
   Andrew's `comment` near the top, then a **Runway** section with one **mini progress bar per
   active tort** (`runway[]`: label = tort, bar fill = `pct`, caption = `used`/`cap` `cap_unit` +
   `est_days_left`), then **ACTIVE** torts and **UPCOMING** torts as small tag lists. If a runway
   `cap` is null, show "no cap set" (no bar).
6. **Footer** — "auto-refresh hourly · retainers daily · shared-password access".

## Status color mapping (from `status` field)

- `green` → green pill / border
- `amber` → amber pill / border (also used for stale/broken data)
- `red` → red pill / border (gross margin < 10%)

## Definition of done

- `index.html` + assets render the mockup's look, populated from `data.json`.
- All `data-contract.md` fields are consumed; no invented metrics.
- The 4 hard rules in data-contract.md are honored (no CPL headline, stale≠0, spend caveats shown,
  Pulaski separate from Broughton).
- Pushes cleanly to the TCS GitHub repo and serves via GitHub Pages behind the shared password.
