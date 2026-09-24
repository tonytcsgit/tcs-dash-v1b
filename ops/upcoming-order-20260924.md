# Operations section order — September 24, 2026

Request: move Upcoming budget priorities directly below Program delivery.

Updated order after the unchanged top priorities/planning cards:
1. Program delivery
2. Upcoming budget priorities
3. Buyer health
4. Prospects
5. Needs Attention

Only the existing section's location changes. The upcoming card HTML, ranks, labels, dates and Not set values are identical. September 24 lawsuit priorities, demo warning, synthetic fixture/model, all other pages, live sources and schedulers remain unchanged.

Validation: observed browser regression fail on the prior order, then pass after moving the section. Four model tests and two Chromium tests passed, including DOM order, actual section geometry, retained content, navigation, mobile overflow and source isolation. JS syntax and diff whitespace checks passed. Sorted renderer lines compare equal before/after, proving a pure line move.

Release scope: operations.js, test_operations_browser.py and this log. Publication uses the existing publisher lock and non-force fast-forward; verify public Pages commit/artifact and rendered screenshot before announcing completion.
