# Task: Build the TCS Internal Dashboard front-end (v1)

You are building the **front-end** for an internal company health + priorities dashboard for TCS
(tort lead-gen). The data pipeline already produces a real `data.json` in THIS directory — you build
the static site that renders it.

**Read these files first, in this order, before writing any code:**
1. `build-brief.md` — the full build spec (tech constraints, layout, brand, definition of done)
2. `data-contract.md` — the exact `data.json` schema. Design against THIS — do not invent fields.
3. `metric-definitions.md` — the meaning of each field (so you render them correctly)
4. `brand-kit.md` — TCS logo + teal/dark palette
5. **`dashboard-mockup.html` — the APPROVED visual mockup. This is the source of truth for layout,
   spacing, and component styling. Use it as your starting HTML/CSS and match its look.**
6. `data.json` — the real data. Open it. Render exactly what's there.

## Hard requirements (will be checked)

- **Static site** — `index.html` + CSS + vanilla JS. No server, no build step required to view.
  It must open and render correctly by simply opening `index.html` (fetching `data.json` from the
  same directory). If you use a framework, it must build to plain static files — but plain
  HTML/CSS/JS is preferred for v1.
- Reads `data.json` via `fetch('data.json')` on load. Handle the file being briefly absent or
  mid-refresh (show a "refreshing…" state, not an error). Auto-refresh every 5 minutes.
- **Consume every field in the contract.** No invented metrics, no hardcoded numbers.
- **The 4 hard rules from data-contract.md are mandatory:**
  1. Never show a CPL headline (CPL is a table column only).
  2. Never render a broken/stale source as a real number — if `data_ok==false` or the tort is named
     in `stale_warnings`, show the amber ⚠️ state, not $0/0%.
  3. `spend_caveat` must be visible whenever set.
  4. Pulaski is its own buyer card — never fold Olympus/Pulaski into Broughton.
- **Status colors:** green `#30a46c`, amber `#f5a524`, red `#e5484d`. Dark background, light cards.
- **Logo** at `assets/logo.png` (white-on-transparent, dark-ready) in the header.
- **Responsive** but desktop-first.

## Layout (top to bottom)

1. Header — logo left; right side `data_freshness` ("Data as of …") + `stale_warnings` as a warning chip.
2. Top row side-by-side: "Needs Attention" card (`needs_attention[]`, red first then amber, each row:
   level pill + name + reason + owner) and "Andrew's Tort Priorities" card (`andrew_priorities[]`
   numbered + `andrew_note` as a highlighted quote callout).
3. Company KPI strip — `company`: spend, revenue, gross profit, margin %, cost/sign, payable leads.
   NO CPL. If `company.caveat` is set, show it.
4. Torts board — a dense TABLE, sorted by spend desc. Columns: Status pill · Tort · Spend · Revenue ·
   Margin % (color-coded) · CPL · Cost/Sign · Leads · Signs · Note (prefix "Andrew:" when
   `note_author` is Andrew). `data_ok==false` rows render in amber ⚠️ state. `spend_caveat` shows
   small under spend.
5. Buyers board — 5 CARDS. Each: buyer name + status pill (top border = status color), Andrew's
   `comment` near top, then a Runway section with one mini progress bar per active tort (`runway[]`:
   label=tort, fill=`pct`, caption=`used`/`cap` `cap_unit` + `est_days_left`), then ACTIVE and
   UPCOMING torts as small tag lists. `cap: null` → "no cap set", no bar.
6. Footer — "auto-refresh hourly · retainers daily · shared-password access".

## Password gate

Add a simple client-side password gate (shared team password, obscure-URL + shared-password is fine
for v1, internal only). Use a lightweight JS prompt/overlay that reveals the dashboard on the correct
password. Hardcode a placeholder password constant `TCS_DASH_PASSWORD` (default `"tcs2026"`) clearly
marked at the top of the JS so it's trivial to change. Do NOT build real auth.

## Definition of done

- `index.html` renders the full dashboard populated from `data.json`, matching the mockup's look.
- All contract fields consumed; no invented metrics; the 4 hard rules honored.
- A `README.md` noting how to view it (open index.html / serve the dir) and how to change the password.

Build it now. Write the files into THIS directory.
