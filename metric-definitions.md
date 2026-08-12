# Metric Definitions — TCS Internal Dashboard (CANONICAL)

Bake these into the pipeline AND show them in a DEFINITIONS.md on the site so the team can't
argue about how a number was computed. Every formula here is the locked rule — do not "simplify."

## Core formulas

| Metric | Formula | Notes |
|--------|---------|-------|
| **Payable leads** | count of intake rows MINUS exactly 3 statuses | see non-payable list below |
| **Revenue** | payable leads × payout/lead | payout from the canonical table below |
| **Spend** | ad spend for the tort, window-matched | source varies — see Spend sources |
| **Gross profit** | revenue − spend | |
| **Gross margin %** | (revenue − spend) ÷ revenue × 100 | **drives the red/amber/green status** |
| **CVR / sign rate** | signed ÷ payable × 100 | signed = `Status == "Signed"` |
| **Cost/Sign** | spend ÷ signed | render `n/a` if signed=0, `—` if spend=0, `TBD` if spend unknown |
| **CPL** | spend ÷ payable | **table column only — NEVER a headline / KPI** |

## Non-payable statuses (EXACTLY 3 — Andrew FINAL Jul 8 2026)

- `Rejected - Failed Prequalification`
- `Rejected - Wrong Number | Spam | Other`
- `Rejected - Existing Contact`

**Everything else is payable — including `Rejected - Doesn't Meet Criteria` (DMC), Do Not Contact,
all Pending buckets, Declined TCPA, Test, Completed Cadence.** DMC IS payable. Never call DMC
"failed prequal" (they're different; the true prequal signal is `Formsite_Knockout_Question` non-blank).

## Status (health) rule — the ONLY automated threshold in v1

- 🔴 **red** if gross margin **< 10%**
- 🟡 **amber** if gross margin **10–25%**, OR the data source is stale/broken (`data_ok==false`)
- 🟢 **green** if gross margin **> 25%** AND data fresh

All other health/status is **MANUAL** (Andrew's comments override / add context). Bands confirmed
by Andrew Aug 7 2026.

## Canonical payouts ($/lead) — from `bp_pnl.py` `VERIFIED_PAYOUTS` (NEVER hardcode ad-hoc)

| Tort | Payout | Note |
|------|--------|------|
| Hernia Mesh | $120 | |
| SMA | $90 | YouTube-driven |
| PowerPort | $200 | |
| Talcum | $500 | dead vertical (removed from PNL Aug 2) |
| **ILM** | **$570 → $670 eff Jul 21 2026** | split by lead date for windows spanning Jul 21 |
| Paraquat | $350 | |
| Endoscopy | $70 | |
| TVM (Transvaginal Mesh) | $120 | new vertical (Jul 26) |
| BM (Breast Mesh) | $100 | new vertical (Jul 26) |

ILM step: for any window spanning Jul 21 2026, score each ILM lead by its own `Created_Date`
($570 before, $670 on/after). Flat $670 only for fully-post-Jul-21 windows.

## Spend sources & their caveats (CRITICAL — wrong spend = wrong margin = wrong status)

| Tort | Spend source | Caveat to surface |
|------|--------------|-------------------|
| Most BP torts | BigQuery `akd_pnl.<tort>_spend_daily` | check `MAX(Day)` — a frozen view ≠ $0 spend |
| **SMA** | **YouTube — MANUAL** | never in Meta pull; `sma_spend_daily` holds YT; mark `spend_source:"youtube_manual"` |
| **TVM / BM** | **Meta API only, PARTIAL** | no BQ view; linkout/YT spend NOT captured → cost understated, margin overstated-pessimistic; mark `spend_source:"meta_partial"` + caveat |
| Olympus/Pulaski | **EXCLUDE from BP entirely** | Pulaski is a separate buyer; never fold into Broughton numbers |

**Stale-source defense:** before reporting $0 spend or 100% margin, check the BQ view's `MAX(Day)`
against the window. If frozen mid-window (Endoscopy froze Jul 14 2026), set `data_ok=false` and add
a `stale_warnings` entry — do NOT report a fake giant profit. Distinguish a frozen view (pipeline
gap) from a genuinely paused vertical (PowerPort/Talcum: view current, truly 0 rows).

## Buyers (fixed set) & their torts

- **Broughton** — the BP torts (SMA, Hernia Mesh, ILM, Paraquat, PowerPort, Endoscopy, TVM, BM, …).
  Runway cap = Callie's **weekly lead quota** per tort.
- **Pulaski** — Olympus (Endoscopy-equivalent), WDC. Retainers via Hochman + RCP ONLY (never BP).
- **Bryan** — Depo (Russ runs day-to-day; list Bryan). Runway cap = total case count (manual).
- **Wagstaff** — Chlorpyrifos. Runway cap = total case count (manual).
- **Parker** — WDC/CAW (LP campaign 35624), Parker RI family. Runway cap = total case count (manual).

## BP weekly lead quotas (Callie, #tcs-bp Slack — change monthly; re-check before trusting)

SMA 1,107 · Hernia Mesh 846 · PowerPort 270 · ILM 48 · Paraquat 35 · Talcum 50 · Endoscopy TBD.
(These feed the Broughton runway bars.)

## LeadProsper campaign IDs (for lead-level pulls)

SMA 29376 · Hernia Mesh 34396 · Depo Provera 23168 · Talcum 20338 · Roblox 26850 ·
Rhode Island JDC 35302 · IL YRT 34742 · PortACath 29172 · Silicosis 35246 · Video Game Addiction 32506 ·
**Parker WDC 35624** (= the CAW feed) · Parker RI 35620 · Parker RI Boarding 35820 ·
Parker RI Clergy 35798 · Parker RI JDC 35822 · Endoscopy 35112 · Olympus 35188.

## Sources of truth (reuse the existing skills — do NOT rebuild these pulls)

- **BP intake sheet** (`1rnqYRHwbDrgoWjztft__fRt-XGEtsfnDD2MtDt9Wcrw`) → payable/signs/CVR.
  Broken-tab defense: scan first 8 rows for the `Status`/`Created_Date` header; if absent, the tab
  is broken → `data_ok=false`, never report 0.
- **LeadProsper** → `leadprosper-reporting` skill (buyers[] split, sell_price, pagination).
- **Meta spend** → BQ `akd_pnl.*_spend_daily` preferred; `broughton_report.py` for live Meta-only.
- **SR reports** → `sr-retainer-status-check` skill (SharePoint keep-rate).
- **Retainers** → CaseOpp `/api/getAggData` + myLegal.cc (see sr-retainer-status-check references).
- **Gmail feeds** → `scripts/gmail_access_token.py` (refresh-token cred, NOT the dead google-workspace OAuth).
