# Data Contract — TCS Internal Dashboard

The single JSON file the front-end reads. The Hermes pipeline (`scripts/build_dashboard_data.py`)
regenerates this every hour (and the retainer fields daily) and git-pushes it; GitHub Pages serves
the site which fetches this file. **Claude Code: design against THIS schema — do not invent fields.**

File: `data.json` (served at the site root alongside `index.html`).

## Top-level shape

```json
{
  "generated_at": "2026-08-07T13:00:00-04:00",
  "data_freshness": {
    "leads_spend_sr": "2026-08-07T13:00:00-04:00",
    "retainers": "2026-08-07T07:05:00-04:00",
    "stale_warnings": ["Endoscopy spend view stale (last Day 2026-07-14)"]
  },
  "company": {}, "needs_attention": [], "andrew_priorities": [],
  "andrew_note": {}, "torts": [], "buyers": []
}
```

## `company` (KPI strip) — window = current quota week (Mon→today)

```json
{
  "window_label": "Week of Mon Aug 3 — Day 5 of 7",
  "spend": 834000, "revenue": 1231000, "gross_profit": 397000,
  "margin_pct": 28.6, "cost_per_sign": 1679, "payable_leads": 7043,
  "deltas": {"revenue_wow_pct": 8.0}
}
```

## `torts[]` (the table) — one object per tort, sorted by spend desc

```json
{
  "tort": "ILM",
  "status": "red",
  "spend": 438000, "revenue": 459000,
  "margin_pct": 4.6,
  "cpl": 603,
  "cost_per_sign": 2940,
  "payable_leads": 726, "signed": 149,
  "spend_source": "meta",
  "spend_caveat": null,
  "data_ok": true,
  "note": "fix margin or pull spend",
  "note_author": "Andrew", "note_ts": "2026-08-07T09:00:00-04:00"
}
```

## `buyers[]` (the cards) — fixed set: Broughton, Pulaski, Bryan, Wagstaff, Parker

```json
{
  "buyer": "Broughton",
  "status": "green",
  "comment": "main engine, healthy",
  "comment_ts": "2026-08-07T09:00:00-04:00",
  "runway": [
    {"tort": "SMA", "cap": 1107, "cap_unit": "leads/wk", "used": 690, "pct": 62, "est_days_left": 3},
    {"tort": "Hernia Mesh", "cap": 846, "cap_unit": "leads/wk", "used": 661, "pct": 78, "est_days_left": 1}
  ],
  "active_torts": ["SMA", "Hernia Mesh", "ILM", "Paraquat"],
  "upcoming_torts": ["Silicosis"]
}
```

**Runway semantics (LOCKED):**
- **Broughton** → `cap` = Callie's **weekly lead quota** per tort; `used` = payable leads this
  quota-week; `pct` = used/cap; `est_days_left` = days until cap at current daily burn.
- **Other buyers (Pulaski, Bryan, Wagstaff, Parker)** → `cap` = **total case count** target
  (manual, from `targets.json`); `cap_unit` = "cases"; `used` = signed retainers to date.
  If no target set, `cap: null` → render "no cap set", no bar.

## `needs_attention[]` — auto-surfaced (red first, then amber)

```json
{"tort_or_buyer": "ILM", "level": "red", "reason": "Gross margin 4.6% — under 10% floor", "owner": "Jordan"}
```
`owner` from comments.json assignments (manual). Auto-surface triggers: status==red, or
`data_ok==false` (amber "pipeline gap"), or a buyer tort >85% of cap.

## `andrew_priorities[]` + `andrew_note`

```json
"andrew_priorities": [{"n":1,"text":"Push SMA volume — best margin, feed it."}],
"andrew_note": {"text":"Focus this week on ILM margin...", "ts":"2026-08-07T09:00:00-04:00"}
```
Both from `comments.json` (Andrew dictates to Hermes → Hermes writes the file).

## Sidecar files the pipeline reads (NOT served)

- `comments.json` — Andrew's per-tort/per-buyer notes + priorities + the top note. Hermes writes
  this when Andrew messages updates. Schema mirrors the note/priority fields above.
- `targets.json` — manual capacity targets (buyer-tort case counts, any non-BP caps). Blank until
  Andrew supplies numbers (LOCKED: do not invent).

## Hard rules for the front-end

1. **Never show a CPL headline.** CPL may appear as a table column only. Lead with spend/revenue/margin.
2. **Never render a broken/stale source as a real number.** If `data_ok==false` or a
   `stale_warnings` entry names the tort, show the ⚠️ state, not $0 / 0%.
3. **`spend_caveat` must be visible** whenever set (TVM/BM Meta-only-partial; SMA YouTube-manual).
4. **Olympus/Pulaski never appears under Broughton.** Pulaski is its own buyer card.
