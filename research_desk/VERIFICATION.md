# Pre-launch verification

Baseline: recovered Research Desk archive version 2 passed 65 Python tests before changes. Supplied standalone attachments were an older/incomplete generation. The GitHub repository was then cloned at d564f027b9a9db8e64d67c5ba7e21ec583fbf65d; its EdgeOdds baseline passed 12 tests. Existing analytical edgeboard and historical Desk folders were preserved.

Current commands and exact output are recorded in `reports/python-tests.txt`, `reports/ui-checks.txt`, `reports/benchmark.json` and repository `docs/prelaunch/edgeodds-tests.txt`. Synthetic API, accounting, provider recovery, snapshot dedupe, rescheduling, live identity, query limits/indexes, CLI and cross-process tests are included. Original analytical edgeboard tests and the historical Desk 2 suite were also rerun independently to avoid module-name collisions.

The minimal DOM entry-logic check and JavaScript syntax check passed. A fresh Chromium browser run was not completed: no executable was installed, and Playwright browser downloads failed as invalid/truncated ZIP responses. Existing screenshots/browser-pass claims from the recovered archive are historical only and are not used as evidence for this release. CI includes a separate browser workflow gate that must pass before browser sign-off.

The synthetic 2,000-quote benchmark measured approximately 0.733 seconds to ingest, 0.0103 seconds for a 100-row latest page and 0.00243 seconds for a 100-row event-history page in this environment. SQLite EXPLAIN confirmed indexed event-history, contract/source-time and user/audit queries. This is a small local measurement, not a production-load claim or a measured comparison against the old code.

No live provider credential was supplied or used; no real bookmaker request, production deployment, real wager execution, external vulnerability-service clearance or predictive-profitability validation was completed. Real state feeds/rules/account availability remain unverified. Software test results do not establish a betting edge.

## Observed final results

- Repaired Research Desk: 86 tests passed (final complete run: 209.939 seconds in this environment).
- Repaired EdgeOdds: 21 tests passed.
- Preserved historical Desk 2: 31 tests passed.
- Preserved analytical edgeboard: 12 tests passed.
- Targeted final HTTP checks, UI entry logic, JavaScript syntax and a clean launcher/authenticated latest-API smoke test passed.
- Fresh browser rendering and live upstream integration remain unverified for the reasons above.
