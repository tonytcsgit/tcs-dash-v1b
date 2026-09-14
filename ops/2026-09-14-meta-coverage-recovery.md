# Meta coverage recovery — 2026-09-14

## Result and deployment boundary

Implemented and live-tested the financial preview's read-only Meta token union. This branch is based on remote main, not the original worktree's unpublished backlog. It is **not a financial-data release** and does not modify the hourly BP UTM job or public `data.json`.

The financial preview implementation previously existed only as untracked files in the original repair worktree. This branch versions that preview together with this task's token-pool/coverage changes. Current working implementation: `/Users/andyoc/tcs-dashboard-builds/v1b-financial-repair/`.

## Live evidence

Reporting window: **2026-09-07 through 2026-09-13**, America/New_York. Preview generated **2026-09-14T21:05:34Z**; canonical credentials read at **21:05:27Z**.

- Local cache: **29** unique tokens, exposing **75** accounts.
- Canonical sheet: **30** unique tokens, exposing **73** accounts.
- In-memory union: **36** unique tokens; **77/77** discovered accounts successfully queried.
- **50** unique account/campaign observations; account ledger reconciled with observation count.
- Recovered canonical-only accounts:
  - `act_1053754337633967` (SP 1): **$79.27 USD** ILM-labeled spend.
  - `act_909229411800824` (DRR 1): **$49.40 USD** ILM-labeled spend.
- Recovered account contribution: **$128.67 USD**. This is the sum of those two accounts, not a claim that every other historical API observation stayed unchanged.
- Current observed ILM spend: **$43,083.80**, still **partial**, not an authoritative total.
- **15** token-discovery failures across the union. The larger credential pool includes stale/redundant entries; this does not mean 15 accounts are missing.
- Six historically mapped accounts remain unresolved. `meta.complete=false` and `financial_complete=false`; missing coverage never becomes zero spend.

## Unresolved access

| Historical family | Account ID | Current treatment |
|---|---|---|
| BM7103 | act_1961087388614841 | Unknown access/retirement |
| BM2968 | act_1755085232182925 | Unknown access/retirement |
| P68 | act_1574584140925575 | Unknown access/retirement |
| P68 | act_852457087359114 | Unknown access/retirement |
| P68 | act_1529841424694585 | Unknown access/retirement |
| Surya | act_595698656203709 | Unknown access/retirement |

Independent read-only access audit found original credentials returning OAuth 190 and tested live alternate credentials returning permission errors for these account reads. Current canonical sheet, local token ledger and Notion access-map review did not establish retirement. Expired credentials or absent registry records are not evidence of zero spend. Resolution requires working account access or dated owner confirmation of retirement and its reporting implications.

The watchlist is historical evidence, **not an exhaustive current business account inventory**. No discovered accounts are dropped merely for being absent from this watchlist. No credential is silently treated as redundant for purposes of financial completeness.

## Implementation

- `meta_token_pool.py`: credential reads only; local-plus-canonical union stays in memory. Vertical sheet token rows parsed independently of labels. Empty/invalid/unavailable/capped sheet reads flag incompleteness while preserving local observations.
- `main_sources.py`: unique-account discovery, alternative-token insight retry, account/campaign deduplication, source-origin counts, canonical-only recovered accounts, per-account observation receipts, historical unresolved-account list.
- `build_dashboard_data.py`: real preview dispatch consumes the union; all union credentials are included in the output secret-leak check.
- `dashboard_config.yaml`: canonical sheet/range plus documented historical watchlist. No hardcoded credentials or guessed retirements.
- Existing BP eligibility, currency conversion, SMA-only YouTube rules, HM pricing gate and production-output rejection remain in place.

## Verification

- **39 tests passed**, including new RED→GREEN regressions for the token union, unavailable/empty/truncated/malformed canonical reads, recovery without double counting, historical gaps remaining unknown, canonical failure blocking complete totals, and actual builder integration.
- Real full preview build completed, not a fixture-generated report.
- Draft 2020-12 schema validation: **0 errors**. Native runtime lacked `jsonschema`; validation succeeded in an isolated `uv run --with jsonschema` environment.
- Account ledger: **77 unique account rows**, **50 observations**, successful account-read count reconciled.
- Private preview permissions verified: file **0600**, parent **0700**.
- Before/after SHA checks verified local credentials, service-account file, local financial snapshot and public financial bytes unchanged.
- Public financial SHA-256 at verification: `05b00cab82bef5c504bf2ab3f8f551b3ce44e3f1493332472a676ba58bce12c5`.
- Static scan of seven staged source/config/test files: no credential literals, shell injection or pickle usage found. An additional live union-credential scan found no actual local/canonical Meta tokens in candidate source, work log or private preview.
- Independent code review: **PASS**, no blocking security concerns or logic errors. Optional follow-ups: distinguish empty-insights transport success from metadata completeness, and add a dedicated first-token-fails/second-token-succeeds fixture. These were suggestions, not reported release blockers.
- Live BP-only scheduled publishing continued independently: successful receipt at **2026-09-14T21:08:26Z**, verified public BP artifact SHA-256 `fef691ad56e5d2bda80bc96950197a72a583e86cb1746c407da4789a02db4fa1`. The release worktree remained clean.

Private audit artifacts (not committed):
- `/Users/andyoc/.hermes/reports/tcs-dashboard-repair/main-preview.json`
- `/Users/andyoc/.hermes/reports/tcs-dashboard-repair/meta-recovery-verification.json`
- `/Users/andyoc/.hermes/reports/tcs-dashboard-repair/meta-unresolved-account-audit.json`

## Reproduction

From the financial-repair worktree:

```sh
HOME=/Users/andyoc /usr/bin/python3 -B -m unittest discover -s . -p 'test_*.py' -q
HOME=/Users/andyoc /usr/bin/python3 -B build_dashboard_data.py \
  --since 2026-09-07 --until 2026-09-13 \
  --out /Users/andyoc/.hermes/reports/tcs-dashboard-repair/main-preview.json
```

Reporting windows must be chosen explicitly for subsequent investigations. Keep the private preview private; do not copy it to `data.json` while financial completeness is false. Do not run the side-effectful token-sync/media-buy modules to obtain credentials.

## Remaining financial gates

This task fixes canonical-token omission. It does not resolve inaccessible historical accounts, SMA effective-dated campaign renames/empty account ingestion, HM intake-source billing evidence, non-BP financial mappings, or unfetched SR/retainer sources.
