# EdgeBoard Next / MarketEdge OS

A new standalone sports research and manual wager tracking app, built from the decisions recovered across all seven accessible GitHub repositories. Existing applications and hosted deployments are untouched.

## Run

Python 3.12+ for the main workspace; Node 24+ and npm for the full research suite. Build the research runtime once:

```sh
cd /workspace/SportsBettingApp/next_app/research_runtime
npm ci
npm run build
cd /workspace/SportsBettingApp
python next_app/server.py --port 8080
```

Open http://127.0.0.1:8080. Use **Open full research suite** for the migrated original tools at `/advanced/`. The Python launcher starts the bundled Node backend on loopback port 8091. Set provider keys before launching when licensed access is available. The server binds to loopback by default. It is a **single-owner app**, with optional workspace-wide password protection, without multi-user accounts or provisioned internet deployment infrastructure. See HOSTING.md before changing the bind address. SQLite databases are created in `next_app/data/`, ignored by Git, and persist across restarts. The initial $1,000 bankroll is a configurable starting setting, not an imported account balance.

## Implemented

- Fresh responsive market board, sport filters, team search, per-book quotes, exact market/line/period evidence, and honest unavailable states.
- Default captured-source mode backed directly by the existing `edgeodds.ingestion.IngestionStore` and versioned EdgeBoard contract. A separate fixed synthetic demo never becomes network data. Loading limits are displayed; the app does not claim a full-board scan.
- Research slip with source/rule checks and explicit reasons to withhold probability, EV and staking. A two-way proportional de-vig calculator labels market benchmarks correctly. Research slips are browser-session state; wager records persist in SQLite.
- Manual paper and actual wager ledgers, actual ticket ID deduplication, UTC daily stake limits, open exposure limits, confirmation of total returned payout, realized P&L, and immutable action audit records. Actual and paper results and limits remain separate.
- Five frozen research reports recovered from EdgeBoard: corrected receiving60, NFL baseline, MLB baseline, halftime validation, independent reception validation. These are inspected without retraining or promoting them.
- EdgeOdds connector health, seven-repository commit provenance, integration coverage, and downloadable JSON workspace reports with mode/source/approval context.
- A live/second-half workspace that identifies missing live evidence and links to the recovered research models.

## Connecting captured odds

For private hosting preparation and the optional workspace-wide password gate,
see [HOSTING.md](HOSTING.md). Public hosting and live provider verification still
require host configuration and authorized provider credentials.

Use an existing EdgeOdds ingestion database:

```sh
python next_app/server.py --odds-db /absolute/path/to/edgeodds.sqlite3
```

For new captures, use the existing `python -m edgeodds --help` CLI. That workflow requires authorized provider access and reviewed native-ID event mappings. Keep credentials in server environment variables. This app neither starts a polling process nor verifies provider licensing. Replay fixtures stay in the fixture partition and are excluded from source mode.

Captured source prices can be stale or unverified; every quote retains the existing contract's reasons and source evidence. Unknown timestamps, model probability, EV, uncertainty and CLV remain unavailable. Missing source data is never described as a successful scan with zero edges.

## Scope carried forward and remaining migration

See [MIGRATION.md](MIGRATION.md). All seven repositories were cloned to `/workspace/sources/`; exact revisions are recorded in [sources.json](sources.json). Repository availability does not establish working hosted integrations.

## Full research suite migration

All EdgeBoard frontend/backend research modules are now included under `research_runtime/`, retaining the original source decisions and model artifacts. A local compatibility layer replaces AppDeploy's router, secrets and database SDK with 73 API routes, environment-only provider secrets, SQLite CRUD/transactions, and a local session owner. The research suite preserves the old UI and tools alongside the new interface. It does not claim hosted multi-user authentication: its sign-in control selects the local owner only.

Provider adapters, free discovery, slip verification, live/halftime research, model scoring, backtests, research pipeline, quote/execution/prediction ledgers and diagnostics are runnable through this suite. External source availability, provider credentials, runtime network permissions and valid input data still determine whether an individual research request succeeds. No provider was marked live-verified. The advanced suite's original wager ledger is separate from the new workspace's ledger; records are not silently merged.

Telegram, subscription billing, automatic notifications and wagering execution are not enabled. No predictive improvement or public deployment is claimed.

## Validation

```sh
python -m unittest discover -s next_app/tests -v
python -m unittest discover -s edgeodds/tests -q
node --check next_app/web/app.js
```

Optional browser check (Playwright and `/usr/bin/chromium` required):

```sh
python next_app/tests/browser_check.py
```

The browser check runs a temporary server with disposable databases, checks desktop/mobile workflows, downloads an export, and produces screenshots under `previews/`. It does not change the running user's ledger or contact sportsbooks.

Validated locally: 7 new backend test groups, 140 existing EdgeOdds tests, JavaScript syntax, and Chromium flows covering demo filtering, slip review, de-vig arithmetic, persistent paper wager settlement, model reports, provenance, export, mobile overflow and browser errors. Synthetic tests establish software behavior, not betting performance.

Additional migrated-runtime checks: `npm run build`, `npm run test:model` (8 pass, 1 real-data cohort check skipped without pinned raw CSVs), `node --test compat/runtime.test.mjs` (CRUD, owner separation, transactions and rollback), and 2 Python receiving-model tests. Browser checks opened the migrated Advanced Research and My Wagers views without JavaScript exceptions. The protected storage diagnostic returned 401 signed out and completed create/read/update/delete signed in.
