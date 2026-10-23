# Sports Research Desk — inspected local continuation

This is the runnable application recovered from `Sports_Research_Desk_Local_Candidate.zip`, expanded and repaired on 2026-10-04. Changes are applied to this package. **They have not been applied to the deployed EdgeBoard app.** Both connected AppDeploy accounts returned Unauthorized for source access to `edgeboard-kshzox`; their accessible app lists did not contain it. Website access alone did not grant source access. The earlier core archive was retained as a reference.

The objective is to discover credible positive EV across all supported sports, books and markets. Discovery does not favor one sport or market. **No evaluated probability model is available, so there are no qualifying opportunities and no model probabilities or EV on the research board.** Price disagreement and market benchmarks never create picks.

## Start

Requires Python 3.10+ and the system IANA time-zone database. The application uses Python's standard library. Unzip, enter `Sports_Research_Desk`, then:

```bash
python3 -c 'import secrets,json; print(json.dumps({"dante":secrets.token_urlsafe(32)}))'
export BETTING_USERS='{"dante":"REPLACE_WITH_THE_GENERATED_TOKEN"}'
python3 server.py --db research.sqlite3 --port 8765
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). Enter the generated token. Each user must have a distinct token of at least 32 characters. The token stays in page memory and is cleared on sign-out; it is not saved in browser storage. Keep environment configuration and database access private. Tokens are server-side credentials, not passwords with account recovery.

This server is deliberately **local only**. Host and Origin checks enforce loopback access. Public deployment requires integration into the existing hosting and authentication system. Do not expose this development server as a public service. Database changes and their audit entries commit together. Limit checks, duplicate checks and settlements use SQLite transactions across connections. Prefer one serving process: provider cooldown and scan locks are per process.

### Optional provider

Set `ODDS_API_KEY` in the server's environment and restart to enable The Odds API retrieval. Do not enter the key in the interface, code, quotes or notes. Obtain an authorized subscription directly from the provider. No credential is included in this package.

The Providers view offers:

- Sport catalog and event lists.
- Recently seen event-market discovery.
- Exact market-key retrieval, including event-specific props and segments.
- A resumable scan across all active leagues, featured/outright odds, current events and recently seen event-market keys, in the selected regions.
- Saved decimal-format snapshot imports, explicitly marked unverified.

The scan uses a breadth-first persisted task queue. Each invocation has a total network request budget of 1–20, including a catalog call when starting a cycle. Continue invoking it until the current cycle completes. Pending tasks, failures and cycle status are returned. Failed tasks retry up to three attempts across invocations. Cycles expire after 24 hours and report the reset. No scheduler, background polling or streaming runs.

**A request budget is not a provider credit cap.** Odds credits depend on markets and regions; retrieving all discovered markets can consume substantial credits. Buttons disclose credit-bearing actions. Region `us` is a starting configuration, not a claim of universal book coverage; supported region codes are configurable as comma-separated values. Discovery keys are recently seen, not an exhaustive provider capability list. See [COVERAGE.md](COVERAGE.md).

Network routes use a fixed HTTPS provider host, validate identifiers and reject redirects. Credential-bearing URLs and response bodies are withheld from errors. Rate limits and server errors start a 60-second cooldown; health shows quota headers and the next retry time. No real provider request was verified in this session because no key was available.

## Workflows

| View | Usable functionality | Boundary |
|---|---|---|
| Discovery / Pregame | Timestamped evidence cards, exact contracts, raw implied and eligible market benchmarks, exclusions, source hashes, text filter and time-zone display | No evaluated probabilities, EV, rankings, qualifying prices or picks |
| Live | Live quote/state entry, reference/period alignment, latency, stale/disconnect/out-of-order rejection | No authorized game-state feed or background monitoring |
| Providers | Catalog, events, exact markets, resumable broad scan, saved snapshots, health/errors | Retrieval code locally tested; live provider coverage unverified |
| Wagers | Editable fields or advanced JSON, proposed/paper/actual modes, single/combinations with legs, notes/model association | Actual means user-reported placement; entering a record never places a wager |
| Settlements | Record/correct buttons on wager cards; revisions, source and reason; provisional/confirmed distinction | Payout is manually supplied; no automatic bookmaker grading |
| Performance | Confirmed settled stakes, net P/L, defined ROI, record, sample size, drawdown and dimensional breakdowns | Paper/actual/proposed and currencies remain separate |
| Exposure | Open/provisional stakes and shared event/group exposures | Conservative full-stake accounting; no inferred dependence or hedge netting |
| Limits | Currency-specific open, daily and shared-group limits; IANA day-boundary zone | Validation of new actual tracking entries; not enforcement at a sportsbook |
| Freshness | Per-user configurable quote/state age, alignment and latency thresholds | Relaxing a threshold does not verify data or a model |
| Coverage / Provider health / Audit | Designed schema, catalog/discovered/observed status, limitations, record histories | Operational coverage remains false until independently verified |
| Evaluation | Chronological descriptive binary prediction audit with baseline comparison | No training, model promotion, uncertainty intervals or profitability finding |

Paper wager entry is the default. Proposed recommendations cannot settle. Imports with unchanged IDs deduplicate; changed content cannot overwrite an immutable quote or wager. An external wager identifier deduplicates within the user and normalized sportsbook. Generic authenticated JSON imports are supported; automated bookmaker imports are unavailable.

Settlement payout **includes returned stake**. Profit = gross payout − original stake − fees. Repeat settlement processing is ignored. Corrections require a higher revision and are preserved in the audit trail. Wins, losses, pushes, voids, cash-outs, partial settlements and dead heats are recorded. Pushes/voids require returned stake; losses require zero gross payout. Combination legs retain imported statuses and rules. There is no automatic sportsbook-specific parlay grading.

A provisional result remains open exposure. Full stake counts toward each shared parent event, leg event and explicit exposure group. New actual records check currency-specific daily/open/group limits in the same transaction as creation. Daily limits use the configured IANA zone (UTC if omitted). No stake escalation after losses is suggested or implemented.

Performance ROI uses **confirmed settled net profit / confirmed settled stakes**. Open stake is shown separately. Drawdown uses cumulative confirmed P/L ordered by settlement instant, aggregating indistinguishable simultaneous settlements. Breakdowns use sport, league, market, book and UTC placement date. There is no currency conversion. Monetary values use two decimal places; currencies/products requiring other precision need a specific money adapter. Deposits, withdrawals and bonuses are outside this wager ledger and never included in wagering P/L.

## Evidence and calculations

Read [CALCULATIONS.md](CALCULATIONS.md) for formulas, matching, settlement and evaluation assumptions. User-imported provenance and `rules_verified` are assertions by the importing user, not independent source verification. Account availability remains unconfirmed. A best comparable observed price is not an executable offer.

Provider event IDs are namespaced and case-sensitive. Exact upstream market keys, points, participant descriptions and segment identifiers are retained. A child market timestamp is used; the parent bookmaker timestamp never refreshes a stale/unstamped child. Unverified book rules remain part of a distinct contract, so potentially different rules are not merged. Different prop statistics, lines, periods, rule versions and pregame/live scopes are never interchangeable.

The board recalculates its exclusion state on each request. Newer suspensions/unknown snapshots invalidate earlier same-contract offers. Same-time conflicts fail closed. Live quotes require the latest exact state ID and period, timestamp alignment, known latency and connection health. There are no live EV signals or alerts to deduplicate because no eligible model/feed exists. Future monitoring, alert cooldowns and model-driven reranking are listed explicitly in [REMAINING_WORK.md](REMAINING_WORK.md).

## Verification

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile core.py engine.py providers.py evaluation.py server.py
node --check web/ui.js
node tests/ui_logic.cjs
```

The optional browser gate uses Node and Playwright with Chromium:

```bash
npm install --no-save playwright
npx playwright install chromium
node tests/browser_workflows.cjs
# Or set BROWSER_EXECUTABLE to an existing Chromium executable.
# Optional E2E_OUTPUT_DIR selects where test screenshots go.
```

The browser test starts its own loopback server, uses synthetic fixtures/test-only credentials and an isolated temporary database, then shuts it down. It deletes the temporary database and never connects to a live sportsbook/provider. The archive contains no production credentials, wager database or preloaded demonstration data. Screenshots in `tests/evidence` are explicitly synthetic test evidence.

See [VERIFICATION.md](VERIFICATION.md) for verified results and [REMAINING_WORK.md](REMAINING_WORK.md) for deployment, subscriptions, feeds and evaluated-model dependencies. Passing software tests establishes software behavior, not a betting edge.
