# EdgeBoard — repaired local Research Desk

This is a complete local application recovered from `Sports_Research_Desk_Local_Candidate.zip` version 2 and hardened against the pre-launch audit. It includes the dashboard, provider adapter, SQLite storage, wagers, revisions, exposure/performance reports and descriptive evaluation. It has **not** been applied to the separate public EdgeBoard deployment.

## Running in under ten minutes

Requires Python 3.10+ with SQLite JSON functions and timezone data. Validation used Python 3.12.14. There are no third-party Python application dependencies, no build step and no npm requirement to run the app.

1. Extract the archive and open a terminal in its `research_desk` folder.
2. Run `python3 launch.py --db research.sqlite3 --port 8765`.
3. Open [http://127.0.0.1:8765](http://127.0.0.1:8765) and enter the token printed in that terminal.

The generated token changes each launch. For stable credentials or several users, set `BETTING_USERS` to a JSON object of distinct user names and tokens of at least 32 characters before starting. Never commit credentials or databases. A restrictive file-creation mask applies to new databases; existing file permissions remain the owner's responsibility. Stop with Ctrl+C. Keep the database for the next launch; back it up before upgrading.

The service intentionally binds to loopback, rejects other Host/Origin values, and does not enable CORS. **It is a local application, not an internet-facing production server.** See `SECURITY.md` for the deployment boundary.

## What works

- **Discovery/Pregame/Live:** current source snapshots, exact market identity, implied probability, freshness/exclusion reasons and comparable observed prices when all checks pass; no invented model probability or EV.
- **Providers:** The Odds API catalog, event/market discovery, targeted odds retrieval, saved snapshot import and bounded resumable scanning.
- **Wagers/settlements:** proposed, paper and user-reported actual records; explicit gross payout, fees and revision history; no wager execution.
- **Performance/exposure:** mode/currency isolation, confirmed profit/ROI, simultaneous-settlement drawdown and conservative shared-event exposure.
- **Evaluation:** chronological binary prediction audit with label-availability/fitted-artifact checks, execution-time prices, metrics and subgroups; no automatic model promotion.
- **API:** authenticated, bounded `/odds/latest` and `/odds/history`, plus dashboard and tracking endpoints.

UI lists load 100 records at a time; **Load more records** continues the list. The text filter operates on loaded records. The latest research view does not load all historical quotes. History remains available through the API.

## Provider setup and failure recovery

An authorized `ODDS_API_KEY` must be set on the server for real requests. Never put the key in chat, the dashboard, source files or imported records. Saved snapshot import works without a key and stays unverified. No key or live quote is included in this release.

Use Providers → Load sport catalog → choose a sport → Retrieve exact markets, or continue a scan with a 1–20 request budget. Extra markets require a provider event ID. The scan queue persists across requests/restarts. Each failed task has at most three attempts; exhausted tasks persist in `/api/provider_failures` rather than disappearing. A new cycle can retry them. A request budget is not a provider billing-credit cap.

Requests time out after 15 seconds. HTTP 429/5xx enters a 60-second cooldown; network/JSON failures enter a 5-second cooldown. Invoke the scan again after cooldown. A restarted process retains its queue/failures but resets the adapter's in-memory cooldown. No unattended scheduler or live state feed runs. Malformed snapshots fail atomically, retaining prior history; stale prices remain excluded. Existing observations never become executable prices simply because a fetch succeeded.

## Identity, dedupe and suspicious prices

Provider event IDs are namespaced by league. Quotes bind the provider/league/source event ID to an explicit canonical event/start time. Conflicting IDs or reschedules reject the import until an operator submits a versioned `/api/event_maps` change. Postponed/cancelled or changed mappings invalidate old prices. Separate source IDs are not merged merely because team names match; neutral-site and home/away display changes do not establish a new event.

Team/book aliases require explicit league-scoped `/api/aliases` entries. No fuzzy matching is used. Configure aliases before importing data; alias changes do not rewrite existing snapshots. Cross-provider merging requires an explicit mapping and matching settlement contracts. The adapter's unverified book rules deliberately prevent unsupported cross-book comparisons.

A database-enforced snapshot fingerprint excludes caller IDs, retrieval time, display names and raw envelope hashes; it includes the economic contract, provider observation, price, status and verification/state metadata. Without an observation timestamp, retrieval time remains part of the fingerprint because sameness cannot be established. Same-ID changed content is rejected. Equal-time conflicting prices stay visible and fail closed. Existing pre-upgrade duplicate rows are retained for audit.

Decimal odds must be finite and greater than one; values above the **local safety ceiling of 10,000** are rejected for review, including potentially legitimate longshots. This ceiling is an engineering safeguard, not proof of correctness or a provider guarantee. The provider adapter explicitly requests decimal format; the core supports American/decimal and explicit positive fractional strings. American magnitudes below 100 and booleans are rejected.

Public manual quote/state imports cannot assert adapter verification. Real fetched prices still have unknown account availability/rules and therefore do not qualify as bets. Live comparability additionally requires matching event sport/league/start, explicit live status, state ID/period, latency and aligned timestamps.

## Verification

```bash
python3 -B -m unittest discover -s tests -v
node tests/ui_logic.cjs           # optional Node-based DOM logic checks
node --check web/ui.js
python3 benchmark.py             # isolated synthetic SQLite benchmark
```

The optional browser gate needs Node, Playwright and Chromium:

```bash
npm install --no-save playwright@1.62.1
npx playwright install chromium
node tests/browser_workflows.cjs
```

`BROWSER_EXECUTABLE` can select an existing Chromium binary. Browser dependencies are development-only. See `VERIFICATION.md` for results from this release, including the browser limitation. Tests use synthetic inputs and isolated temporary databases.

The compatible CLI accepts JSONL predictions:

```bash
python3 evaluate.py history.jsonl --train-end 2024-01-01T00:00:00Z --validation-end 2024-12-01T00:00:00Z --output report.json
```

It refuses to overwrite a report and records dataset/code hashes. Its schema is in `API.md`. A successful calculation is not predictive validation. No historical performance improvement or profitable betting model has been established.
