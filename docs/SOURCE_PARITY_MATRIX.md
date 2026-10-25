# EdgeBoard source parity audit — October 25, 2026

## Compared sources and evidence limits

Destination: existing SportsBettingApp release `0de472f`, inspected in a disposable checkout of the same repository. Master source: `danteclaird98/sports-betting-master` pinned `95d5e37a85a3faa2d7942a9c90b631a0c0471309`, specifically `apps/edgeboard/`. This comparison does not infer deployed source from a public URL. Actual AppDeploy source pin `1792966364427` was subsequently recovered at `/private/tmp/edgeboard-hosted-current-20261025`; the six requested source files below were inspected directly. This is source comparison, not a claim that the destination has been deployed there. No private records, provider requests, credentials, or hosting resources were accessed.

Comparison normalized only import paths (`runtime/sdk`, `runtime/client`, transient store). At unchanged baseline: source frontend 31 identical and 8 different files; backend 62 identical and 13 different; shared 5 identical and 2 missing; research 2 identical. Additional destination gateway files are outside the Master source set. Binary identity is not a claim of successful vendor integration.

## Material deltas and disposition

| Capability / exact files | Baseline source parity | Finding / disposition |
|---|---|---|
| Public scans / `backend/engine.ts`, `context.ts`, `gameLines.ts`, `altOdds.ts`, `nflContext.ts` | Missing cost-control behavior | Master defaults `allowProviderRequests=false`; destination previously consulted configured provider secrets automatically. Restored Master’s server-controlled default guards; client JSON cannot grant capability. Free public research remains separate. |
| Caesars / `backend/caesarsFeed.ts`, `src/CaesarsFeed.tsx` | Missing cost-control behavior | Previously a price-loading GET and UI could consume configured credits. Restored zero-credit `OPT_IN_REQUIRED` status and empty quotes without provider or secret access. UI directs users to separately authenticated, budget-confirmed supported live workflow. Credentials alone never authorize a request. |
| Daily scan / `src/DailyDashboard.tsx`, `backend/allSportsReport.ts`, missing `shared/dailyReport.ts`, `dailyScanStatus.ts` | Missing newer behavior | Destination casts untrusted HTTP data and conflates empty board/model conclusions; no display expiry, post-start filtering, per-source diagnostics, or expired-copy gate. Master has strict parser, at-most-60-second display policy, sport-local candidates, source failure/unsupported/unknown differentiation. Restored these source behaviors and their regression tests. This policy is display expiry, not verified source freshness. |
| Navigation / `src/App.tsx` | Missing newer behavior, destination additions preserved | Master hash routes preserve back/forward/reload and independent-model section; destination has same-app return link and OddsBackend component. Union needed; do not overwrite destination gateway. |
| Private local drafts / `src/AccountSlipWorkspace.tsx`, `WagerTracker.tsx`; Master `runtime/transient-store.ts` | Missing privacy change | Destination retains drafts/preferences in persistent browser localStorage; Master uses transient tab memory. Preserve old browser wager import explicitly, never silently copy or delete existing records. Server ledger remains authoritative saved state. |
| Model inspection UI / `src/CorrectedReceivingLab.tsx`, `index.css` | Missing stronger validation/usability | Master validates HOLD/false approval flags, artifact hash/time agreement, metric/count consistency before displaying integrity state; supports provenance/export and inspectable diagnostics. Destination has simpler type casts and limited presentation. Restored the inspection UI and additive model CSS while preserving the stronger scoring module. Added tested timezone, coherent artifact/approval, metric-count and safe-integer validation. |
| Assistant export / `src/AssistantReport.tsx` | Destination improved routing | Destination same-origin `/research-api/api/assistant-report` link retained; Master offers JSON copy/download. Both are user-driven. Do not reintroduce old AppDeploy URLs or alternative root app. |
| Frozen receiving model / `backend/correctedReceiving.ts` | Destination improved | Destination safe-integer history checks and `receiving60Prediction` API receipt are stronger than Master. Preserve. Frozen artifact/manifest/report unchanged; HOLD and execution=false remain mandatory. |
| Forecast source reader / `backend/receivingForecast.ts` | Destination improved | Destination allows only fixed public evidence URLs plus constrained GitHub release-asset redirect, bounded response size/time, cancellation, safe integer yardage. Do not regress to unconstrained fetch. |
| Forward outcomes / `backend/receivingForwardEvaluationCore.ts` | Destination improved | Destination rejects unsafe integer final yardage. No forecast receipt mutation or automatic settlement/trade authorization. |
| Forward persistence / `backend/receivingForward.ts` | Destination adapted | Uses existing `RESEARCH_DB` before fallback, preserving private backup/volume; Master default separate `data/edgeboard.sqlite3` is inappropriate here. |
| Execution evidence / `backend/executionEvidence.ts` | Formatting-only delta | Destination spreads `id` redundantly; both filter owner and omit ownerUserId from returned entries. Evidence remains user reported, never venue-verified execution. |
| Route union / `backend/index.ts` | Destination additions | Seven read-only odds gateway routes and `/api/receiving60/predict` added to Master route set. New receiving-forward routes preserve requireAuth and expected owner comparisons. Keep route union. |
| Receiving forecast/log/evaluation frontend + remaining shared helpers | Same after import normalization | Forward receipt/evaluation modules, outcome helpers, seed and validation data are present. Availability depends on source access and exact evidence; not a betting approval. |
| Exact account slip / `backend/accountSlipAudit.ts`, `shared/accountSlip.ts`, `src/AccountSlipWorkspace.tsx` excluding storage delta | Same logic | Exact legs, payout/rule inputs and report logic preserved. This is not proof of screenshot OCR or venue entitlement. Actual screenshot import workflow still requires separate UI verification. |
| Wager and settlement ledger / backend ledger modules and `src/WagerTracker.tsx` excluding storage delta | Same logic | Existing proposed/paper/actual records, saved ledger, exposure and settlement behavior preserved. User-reported actual remains distinct from confirmed venue fills. No executor added. |
| Live research, SGO owner sessions and provider budget workflows | Same source modules | `shared/sgoOwner.ts` and live research modules unchanged. Source equality does not prove external vendor credentials, delivery, current prices, or public multi-user isolation. Existing single-owner private hosting auth still applies. |
| Python provider import/movements | Destination addition from Master pure converters | Isolated UNVERIFIED manual observation tables; atomic receipts and request/payload replay protection; not an input into verified board/EV. No network SDK entry point. Supported source shape does not authenticate imported claims. |
| Eight `sources/` snapshots, optional SDKs and alternate Master root server | Reference / deliberately not copied wholesale | Preserve pinned provenance and useful existing integrations; do not initialize another app, duplicate ledgers, run optional SDK fetches, or overwrite the existing runtime with Master’s independent server. |

## Fresh validation

Unchanged destination baseline: bundled Python 3.12 `-m unittest discover -s next_app/tests -v`: **35 passed**, `/tmp/parity-baseline.log` (local scratch evidence).

Provider control repair: bundled Node `--test next_app/research_runtime/tests/parity/providerCosts.test.mjs`: **1 passed**, `/tmp/parity-provider-cost.log`. The test bundles the real transitive modules, makes secret-store access fail, and supplies synthetic transports for all public reads. It observes no fetch for default Caesars or empty context, no credential-store access across default scans, and no keyed-vendor requests across alternative odds, KYM, and normal scans. It makes no live provider call. Daily scan parity: bundled Node `--test next_app/research_runtime/tests/parity/*.test.*`: **21 passed**, including parser validation, kickoff removal, expiry, filters, source failure/unsupported distinction and actual bundled provider-control tests; `/tmp/parity-daily-tests.log`.

Model inspection parity: new bundled TSX guard regression rejects conflicting hashes, enabled approval flags, mismatched diagnostic counts, invalid probability and timezone-free artifact clocks. Combined parity suite **22 passed**, `/tmp/parity-model-tests.log`.

Full app/browser/container validation must be run against the final combined tree by the release coordinator; this audit does not substitute for it.


## Actual current AppDeploy source comparison — pin 1792966364427

Source export inspected directly, not inferred from rendered labels. The recovered six-file comparison supersedes earlier uncertainty for these files only. No private records were read or migrated.

| Current-host file | Compared with pinned Master | Destination disposition / concrete gap |
|---|---|---|
| `src/DailyDashboard.tsx` | Identical except trailing newline | Restored destination source has its strict parser, expiry, upcoming filtering and coverage diagnosis. |
| `backend/allSportsReport.ts` | Identical except trailing newline | Restored source preserves source health/model blockers and refreshAfter. |
| `src/App.tsx` | Formatting plus removal of Master root return link | Destination retains one-app return link, direct model tab and persistent hash navigation, with additional odds gateway. |
| `src/AccountSlipWorkspace.tsx` | Host keeps localStorage drafts; Master uses transient tab storage. Other changes are formatting. | Explicit user-controlled draft storage/privacy must be preserved or clearly disclosed. No evidence of newer screenshot OCR or venue execution feature in this file. |
| `src/WagerTracker.tsx` | **Material newer behavior:** `ledgerClientState` protocol, expected revision, durable pending write identity, owner checks before/after transport, response-owner verification, load-generation races, reconciliation without automatic resend, recovery/retention of manual drafts. | Initial destination write-in-flight/draft-retention fix is insufficient for current-host parity. Coordinator/safety reviewer notified to integrate recovered protocol and dependencies before claiming parity; never overwrite destination storage or submit private records. |
| `backend/index.ts` | **Material newer behavior:** owner guards and owner-tagged ledger results; SportsGameOdds status, authenticated refresh and history routes with expected-owner checks. | Preserve destination receiving60 and seven odds gateway routes while unioning these recovered current-host routes and dependency modules. Current credentials/provider authorization remain separate requirements. |

Recovered module provenance (SHA-256 of exact local exported bytes):

- `src/App.tsx`: `f2d9d7bcb7731cea31414d6e350d21d5b09cf338925a22c14d901da776e528a9`
- `src/DailyDashboard.tsx`: `e40706734e710b773906b66af635dae0587b0191828e9bab39f2f53ce634646e`
- `src/AccountSlipWorkspace.tsx`: `694b9595a9870de11422200f61e2c4a8cfe2b96201f5a6284c32a831386a6711`
- `src/WagerTracker.tsx`: `71fc48c07f62a0c8fd867c3bff48823862baeb17d198a9457d88c2d4a00cb4c3`
- `backend/index.ts`: `acdddd94b6662d8bfdd4fb4b2c2b37a04a8fd8d2c039d3b406b8f381a0ca243d`
- `backend/allSportsReport.ts`: `89a47511afce8ab2fc971bc7b4dd8f4d1d3700d1e3b122de303c95615266753f`

## Coordinator integration disposition

The restored direct Independent Model tab and hash/back/reload navigation retain
existing Models & history links and the destination odds gateway. SDK auth sign-in
now returns the documented `{user}` wrapper; this fixes the migrated ledger sign-in
workflow without changing outer private-workspace authentication.

Actual-host wager client and shared owner/input/recovery helpers are integrated.
Its recovered backend remains legacy whole-ledger replacement: revision receipts,
CAS and automatic commit reconciliation are **not** implemented by that backend.
The UI must retain its explicit legacy fallback and unknown-write warning.

The actual-host SGO core/routes/store are integrated. The local continuation uses
an isolated SQLite implementation of its conditional reservation transactions in
the existing research database, rather than falsely assuming the older compatibility
SDK implements conditional writes. Reservations, replay, failed receipts, restart
and owner isolation are tested with synthetic transport. Redirects carrying provider
credentials are refused. No provider key or live request was used. This is backend
capability, not a running monitor or verified licensed feed.

The independentReception artifact/validation JSON values are identical to the
current hosted export. Four related modules (independentReceptions,
receptionFeatures, propEventEvidence, verifyProp) emit identical minified JavaScript
with esbuild after TypeScript/format normalization. They were preserved, not retrained
or promoted. Source equivalence is not live performance validation.
