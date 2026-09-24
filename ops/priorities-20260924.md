# Operations lawsuit priorities — September 24, 2026

Andrew requested this exact replacement of the screenshot's Lawsuit priorities list:
1. Olympus — BP + Parker
2. SMA — Parker + Pulaski
3. CHLOR — BP + DIF
4. Rideshare — BP

Scope: static Operations priority context only. The list's as-of date is September 24. The banner distinguishes this revision from the unchanged September 12 upcoming-budget context. Demo warning, fixed September 16 example clock, fictional metrics, upcoming budgets, model/fixture, other pages, data artifacts and all schedulers remain unchanged. This does not launch campaigns, assign targets or change commitments. The separate unpublished LP feature is excluded.

Verification before publication:
- Browser regression failed on the old five-item list before implementation.
- Updated Operations Chromium suite: 2 passed (exact priority text/order/date, no live requests, retained sections/navigation, mobile width, fixture failure).
- Operations calculation model: 4 passed.
- JavaScript syntax and git diff whitespace checks passed.
- Local screenshot inspected at /tmp/tcs-ops-priorities-local.png.

Release procedure: exact four-file scope (operations.html, operations.js, test_operations_browser.py, this log); coordinate with existing publisher lock, push without force, fast-forward clean release checkout, verify Pages build and public HTML/JS bytes, then rerun public browser checks. A local test is not a deployment receipt.
