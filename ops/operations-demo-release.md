# Operations — synthetic design preview

## September 12 priority context — demo remains a demo

Andrew supplied the ranked lawsuit and upcoming-budget brief and explicitly requested its use as demo context, not live-data activation. The top list now preserves SMA BP/Parker equal importance with Pulaski lower, followed by WDC/Parker, IL JDC/BP, Chlorpyrifos/BP and Rideshare/BP. Upcoming budget cards show Parker Olympus first, Parker Chlorpyrifos second, and Parker Dupixent/Apple AirTag tied third. No amounts, dates, platforms or commitments were inferred for those upcoming budgets. Replaced generic upcoming launch cards rather than attaching their fictional dates to these budgets. Other metric/health examples remain fictional and isolated; updated banner distinguishes supplied priority context from synthetic metrics. Browser tests assert exact order, buyer assignments, equal ranks and unchanged demo isolation. No deletion of other sections was inferred from the unanswered screenshot question.

## Layout revision — remove top controls and KPI strip

Andrew requested removal of the screenshot's Buyer/Platform/Stage/search/Reset bar and all four summary cards, on Operations only. Removed their markup and event bindings; the full example scenario is always shown. Priorities, launch board, program delivery, buyer health, prospects, Needs Attention and example-data warnings remain unchanged. Browser regression first failed with both sections present; revised acceptance checks require absent controls/cards, intact boards and drill-down, no JavaScript errors, mobile fit, navigation and synthetic-only requests. No data artifacts, metrics, source integrations or hourly publisher code changed.

## User-approved scope

A separate Operations page, linked from the existing dashboard navigation. Program grain: tort × buyer × platform. The unit is lead volume; buyer commitments and marketing forecasts remain separate. Andrew owns launch dates and targets for now.

The subsequent user correction is controlling: **example data only; no actual real-life data for now.** Every operational value on this page is synthetic. Andrew's planning-owner role is the only real governance setting; fictional owners are used for marketing and operations examples. No actual business priorities have been copied into the page.

## Files and isolation

- `operations.html`, `operations.css`, `operations.js`: standalone read-only page.
- `operations-model.js`: pure metric/validation functions.
- `operations-demo.json`: 8 deliberately fictional Example programs and 3 Example buyers, fixed end-of-day September 16, 2026 scenario. Not current events or forecasts.
- `index.html`: one navigation anchor only.
- No changes to existing builders, publisher, cron definitions, financial `data.json`, BP `bp_utm_data.json`, Supabase, source Sheets or ad accounts.
- The earlier real-data Operations feed work is isolated in a different unpublished worktree and is **not included** in this release.
- The new page requests only its own synthetic JSON, scripts, styles and the existing logo. It does not load `app.js` or financial/BP datasets. CSP restricts requests and script/style execution to the same origin. This is not an authentication control; the demo contains no private data.

## Design

Priorities and planning ownership → filterable summary → upcoming launches → live program delivery → buyer health → separate prospects → Needs Attention.

Includes buyer/platform/stage/search filters, reset, and expandable program details. Each issue has an example owner and next action. No edit, send, notification or campaign-write controls.

Lead volume in this example means buyer-received leads. Submitted and accepted figures are separate example funnel stages. This is an illustrative definition, not approval of a production source reconciliation rule.

Buyer commitment and marketing forecast each apply to the explicitly displayed target period. Expected-to-date uses uniform calendar-day pacing, inclusive of the scenario date and capped at the period end. Business-day/ramp rules remain unapproved. Buyer rollups cover live programs only and sum each program's own elapsed target period, not an unstated shared weekly quota.

Unavailable feed → unknown volume. Missing commitment → no target, not zero. Future launches and prospects are not scored behind. Incomplete buyer totals are withheld; known subtotals and coverage counts remain explicitly labeled. In this fixed fixture, fresh plus empty observations means a verified synthetic zero (Grove); unavailable plus empty means unknown (Cedar). This convention must not be repurposed as evidence of production-source completeness.

## Verification before publication

- Four Node model tests passed (pacing, commitment/forecast separation, unknown/zero, future launches, buyer coverage and synthetic-data guard).
- Two Playwright tests passed (desktop/mobile, filters/reset, details, exact request-origin/path allowlist, navigation click, no JS errors, failure state, section order).
- Combined existing BP parser/builder/publisher/wrapper regressions plus Operations browser tests: 24 passed. Existing Python 3.9 dependency deprecation warnings remain; no runtime errors.
- Independent read-only review: PASS, no shipping blockers for the fixed synthetic scenario. Additional invalid-JSON/demo=false/date and XSS checks passed in the reviewer harness.
- Parent validated Example Atlas: 180 received / 300 expected / 360 forecast-expected / 45 submitted-received gap. Example North: 357 received / 460 expected, 3/3 volume and target coverage. These are synthetic checks, not business results.
- Screenshot inspected; desktop sections render and mobile document has no horizontal overflow (table scroll stays contained).

Reproduce from this worktree with a local static server on 8878:

```
node --test test_operations_model.cjs
/usr/bin/python3 -B -m unittest test_operations_browser -q
```

For public verification, set `TCS_OPS_URL=https://tonytcsgit.github.io/tcs-dash-v1b` and run the browser suite. Browser tests block financial `data.json` during the existing-dashboard navigation check. Deployment requires scoped commit/push, Pages built status, exact public bytes, and actual public browser rendering. Do not infer deployment from this prepublication note alone.

## Before any later live-data release

Obtain approval to replace examples; establish buyer-received volume/source definitions, target periods, ramp/calendar rules, source completeness and update ownership. Validate phase/date consistency for editable scenarios. Do not silently switch this page to live APIs or merge the abandoned real-data branch.
