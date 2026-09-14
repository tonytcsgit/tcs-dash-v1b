# Dashboard recovery — 2026-09-14

## Scope
- Release assembled from remote `main`, not the original local `main` backlog.
- Original worktree `v1b-with-mock` and its 223 unpublished commits are preserved. Do not push that branch as a recovery shortcut.
- Production release worktree: `/Users/andyoc/tcs-dashboard-builds/v1b-release`, branch `recovery/bp-utm-layout-20260914`.
- Restored HM same-spreadsheet raw fallback; no source sheet edits, no new financial figures.
- Company/Andrew priorities remain at top, Needs Attention below tort/buyer boards.
- Main `data.json` remains the historical August 31 artifact. Prominent warning and footer explicitly identify frozen/unverified financials; do not use its margins, quotas or health badges for current decisions.

## Pre-publish verification
- 9 parser/build/render regression tests passed; `node --check app.js` passed.
- Fresh BP Sheets build: 11 torts, 21,293 payable leads, 2,695 signed, generated 2026-09-14T20:36:09+00:00.
- Independent read of the same spreadsheet's raw source reconciled HM 4,305 payable / 358 signed and SMA 10,264 payable / 1,302 signed exactly.
- Six rendered filter cases passed: lifetime all, HM campaign lifetime, SMA YouTube creative, HM Meta/Morane campaign, high group minimums, empty future window.
- Dataset has only date/platform/marketer/label/campaign/signed fields per lead; no claimant identity/contact fields.
- Local screenshot verified warning prominence, section order and rendered data.

## Main financial release gate — still blocked
- Verify complete Meta account coverage, rather than treating successful redundant tokens as full coverage.
- Verify HM billing-tier mapping from billing evidence; an HQ campaign suffix alone is insufficient.
- Align BP SMA YouTube reporting with available completed-day coverage; no fabricated zero on missing dates.
- Do not enable old legacy financial builder or replace financial timestamps with refresh time.

## Publication verification
- Initial repair published in `7a62e338ce620f7275e9b030c8575223e528f5ef`; GitHub Pages reported `built` for that exact commit.
- Public `bp_utm_data.json` SHA-256 matched release bytes: `7bb2d0fd5eab41c9291cd8d3fe99af6f370d018617eba3b4dad21c0cab510402`.
- Public `app.js` matched release bytes. Live dashboard browser regression passed without JavaScript errors; six live BP filter reconciliations passed.
- Live HM lifetime screenshot confirmed 4,305 payable / 358 signed / 8.3% CVR.
- Follow-up `b14a1bd9657a6c9d4e86e3786d984d8000ca60fc` restored only current Andrew priorities from the read-only comments sidecar. All financial JSON values and original generated_at remain unchanged. Pages built this commit; public priorities and screenshot verified.

## Hourly recovery scope
- Existing job `09b697bd79f7` now targets `tcs_bp_utm_delivery.py`, not legacy `tcs_dash_regen.sh`. No duplicate schedule created; origin failure routing preserved.
- Reviewed runtime implementation lives in this release worktree: `refresh_bp_utm.py` + receipt-checking `cron_bp_utm.py`.
- BP UTM ONLY. Never rebuild financial `data.json`. Main financial release gate above remains blocked.
- Job stays paused until the production entry succeeds and its public-verification receipt is checked. Activation proof will follow.
- Legacy worktree and financial wrapper remain preserved for investigation, not authorized production inputs.
