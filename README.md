# TCS Internal Dashboard (v1)

Static front-end for the TCS company health + priorities dashboard. Renders `data.json`
(produced hourly by the Hermes pipeline; retainer fields daily) per `data-contract.md`,
matching the approved `dashboard-mockup.html` look.

## Files

- `index.html` — the dashboard (single page, no build step)
- `styles.css` — styling (dark theme, light cards — from the approved mockup)
- `app.js` — password gate + fetch/render logic
- `data.json` — the data (written by the pipeline; the site only reads it)
- `assets/logo.png` — TCS logo (white-on-transparent, dark-ready)

## How to view

Serve the directory (recommended — avoids browser `file://` fetch restrictions):

```bash
cd <this directory>
python3 -m http.server 8080
# open http://localhost:8080
```

Or just open `index.html` directly (works in Safari/Firefox; Chrome blocks local
`fetch` on `file://`, so use the server above or GitHub Pages).

In production it's the GitHub Pages site for this repo — the pipeline git-pushes a
fresh `data.json` hourly and the page re-fetches it every 5 minutes automatically.
If `data.json` is briefly absent mid-push, the page shows a "refreshing…" badge and
keeps the last good render (no error, no fake zeros).

## Password

Shared team password, client-side gate only (obscure-URL + shared-password, internal v1
— NOT real auth). To change it, edit the constant at the **top of `app.js`**:

```js
const TCS_DASH_PASSWORD = "tcs2026";   // <<< CHANGE PASSWORD HERE
```

The password is remembered for the browser session (sessionStorage).

## Guardrails baked in (from data-contract.md)

1. CPL is a table column only — never a headline KPI.
2. Stale/broken sources (`data_ok == false` or named in `stale_warnings`) render as
   amber ⚠️ rows — never as $0 / 0% / fake margins.
3. `spend_caveat` (and `company.caveat`) are always shown when set.
4. Pulaski is its own buyer card — never folded into Broughton.
