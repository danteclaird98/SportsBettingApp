# One EdgeBoard application

EdgeBoard / MarketEdge OS is one application in this SportsBettingApp repository. The main workspace (`/`) and preserved research tools (`/advanced/`) are sections of that app, served behind the same private hosting authentication. `next_app/` is an internal source directory; “Next” was a development label, not another app for the user to choose.

## Release source and preservation

The current release work builds on `codex/render-private-api` commit `09fedbb02e688d5b970a6d2cc64627cd5dcc5dc0`, including the earlier EdgeBoard migration and all existing EdgeOdds modules. The recovered AppDeploy source version `1792803491529` also supplied the tested read-only aggregation gateway and stored-odds diagnostics. These are now part of the migrated runtime rather than a separate app.

Original research, exact slips, public props, live/second-half analysis, model reports, manual actual/paper tracking, receipts, audits and diagnostics remain. No original route, model artifact or ledger was removed by this consolidation. Existing hosting and records must remain intact until a verified cutover. The workspace and earlier research ledger stores retain their provenance; records are not silently combined or converted into venue-confirmed fills. Private AppDeploy records still require an authorized, validated export before any import.

GitHub holds the source, review history and automated tests. The prepared single private Fly deployment serves the app and uses one persistent volume; it is not a replicated database. The old AppDeploy site is retained during cutover, not overwritten blindly. Fly hosting account authorization remains required; no live release, account permission, migration or provider access is implied by a green CI result.

## Existing aggregation service

The stored-odds panel under Research tools → Advanced Research → Bookmakers & diagnostics reads the existing Python aggregation service through fixed GET-only routes. Configure `ODDS_BACKEND_URL` and `ODDS_BACKEND_READ_TOKEN` on the server; the Python service must use the same `ODDS_API_READ_TOKEN`. Credentials never belong in the browser or repository. Without an owned HTTPS service and matching credential, the panel explicitly reports NOT_CONFIGURED. No provider refresh or wagering is triggered. This preserves the Python backend boundary rather than rewriting it in the Node runtime.

Mock observations remain synthetic. Storage retrieval times do not establish source quote freshness. Source clocks, equivalent settlement rules, account-executable prices, calibrated model evidence and EV remain unavailable unless separately established. Financial execution stays disabled.

## Verification for this consolidation

On the exact unchanged source, 22 workspace tests passed in a temporary filesystem checkout. Two earlier runs under the cloud-backed Documents directory timed out reading the model catalog; neither was counted as a pass. After consolidation: 22 workspace, 140 EdgeOdds, nine gateway and two compatibility/authentication tests pass; frontend and backend compile. Frozen-model, browser and CI outcomes must be recorded separately when executed. These checks do not establish a live Fly deployment, live vendor data or profitability.

## Launch gate

Complete the Fly browser sign-in opened by the trusted CLI, inspect/reuse any existing app and volume, set private credentials through a secure channel, validate the actual account configuration, then deploy and verify private login, readiness, original research navigation and disposable persistence/restart behavior. Keep the existing deployment and private records until those checks pass. Do not repeat the already completed single approved daily scan or enable financial execution.
