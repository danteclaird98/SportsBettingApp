# EdgeBoard remaining-issues safety review

Reviewed against base `a010941`, October 25, 2026. This review used public source and isolated synthetic tests only. No private ledgers, provider credentials, live scans, paid resources, deployments or financial execution were accessed.

## Fixed findings

1. **Forecast source redirects trusted arbitrary destinations.** `receivingForecast.ts` previously used Fetch's automatic redirect policy. A source redirect could follow an unrelated origin, including an internal address, while the evidence record still named the original public source. The source URLs themselves were fixed server constants, so this was an upstream-redirect trust defect, not a user-supplied-URL endpoint. Forecast reads now permit only canonical schedule/stats URLs, refuse schedule redirects, manually follow at most three signed GitHub release-asset hops, reject non-HTTPS origins, credentials, nonstandard ports, fragments and unexpected paths, share a 20-second signal across hops/body reads, and cancel rejected/oversized bodies. Signed asset URLs are not saved as provenance.

2. **Unsafe receiving-yard integers could influence forecasts or evaluation.** The forecast's current-season CSV parser and historical seed check used `Number.isInteger`, as did the forward evaluation's final outcome guard. Values outside JavaScript's exact integer range could pass validation. These paths now require `Number.isSafeInteger`; invalid final outcomes remain unresolved and do not enter Brier/log-loss scores. The existing outcome adapter already enforced safe integers; a regression assertion now covers its precision boundary.

## Provider-import review handoff

The newly added importer was also inspected. A synthetic 1000-digit integer raised `OverflowError` inside numeric validation before the magnitude bound, escaping the HTTP handler's validation-error response. This was reproduced without a write and repaired by the provider-bridge owner. An independent rerun confirmed a normal `ValueError` rejection and zero stored observations; direct and HTTP regression checks belong to the provider-bridge suite. Imported observations remain explicitly UNVERIFIED, separate from the verified board and wagering ledgers; movement grouping includes provider/native event/native market/book/selection/period/rules, with timestamp conflicts suppressed.

## Reviewed boundaries

- Forward receipts are keyed by frozen artifact/player/game identity; repeated saves return an existing verified receipt. Source-derived forecast probabilities, model hashes, pregame lead time and immutable receipt hashes are checked before saving or evaluation.
- SQLite forward receipt uniqueness and update/delete rejection are enforced in SQL. Restart, duplicate-write recovery, pagination ownership and corruption checks remain covered by the existing isolated suite.
- Public workspace access requires the existing outer private-workspace authentication. Browser research proxy requests additionally require the workspace token; cross-site POST requests are rejected. Bearer clients are bound to `local-owner`; the loopback research runtime recognizes only that owner. This remains a single-owner private application, not a validated multi-tenant authentication system.
- Model probabilities remain conditional research estimates with HOLD, unverified participation/publication clocks, and execution disabled. Frozen artifacts and canonical hashes were not changed.

## Verification

Node 24.19 bundled runtime commands, run in the actual integration checkout:

- `node --test next_app/research_runtime/tests/master/receivingForecast.test.ts next_app/research_runtime/tests/master/receivingForwardEvaluationCore.test.ts next_app/research_runtime/tests/master/receivingForwardOutcomes.test.ts`: **38 passed, 0 failed, 0 skipped**.
- `node --test next_app/research_runtime/tests/master/*.test.ts`: **55 passed, 0 failed, 0 skipped**. Log: `/tmp/edgeboard-safety-master-tests.log` (local evidence, not a hosted-service result).

These synthetic transport tests verify allowed/blocked redirect destinations, a shared timeout signal, bounded loops, header and streamed-body limits, cancellation, unsafe source yardage rejection, unsafe outcome non-scoring, existing model math, and archive/evaluation behavior. They make no external requests.

## Remaining verification boundaries

This review does not establish hosted access, Render account ownership or billing authorization, credentialed odds coverage, historical data sufficiency, forward model performance, profitability, or a production deployment. Provider-import implementation and combined-app acceptance are owned by the coordinator/implementation agent and require their own recorded results. No real-money execution is enabled.
