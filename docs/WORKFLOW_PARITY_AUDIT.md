# EdgeBoard workflow parity audit

October 25, 2026; integration base `0de472f`. Public source and isolated synthetic databases only. No user ledgers, accounts, provider scans, paid calls or financial actions were accessed. This is local contract/source verification, not hosted acceptance.

## Findings repaired in this slice

- **Two preserved ledgers looked like one total.** The root workspace uses `workspace.sqlite3:wagers`; advanced My Wagers uses `/api/wager-ledger` in research storage. Neither view includes the other's stake, P/L or limits. Both now prominently label their scope, explain that records/totals remain separate and unreconciled, and link to the other part of the same app. No records were moved or merged.
- **Research form cleared before save confirmation.** Adding a research wager now awaits the save result and verifies returned count before clearing. A failed/ambiguous write retains the draft and disables edits until explicit saved-ledger reload. A ref rejects concurrent in-flight submissions. No uncertain write is automatically retried. Response count is an acknowledgement, not a durable read-after-write or version/conflict guarantee.
- **Drawdown lacked ordering disclosure.** Advanced calculations sort by wager placement time. The UI now calls this placed-order drawdown and states that it is not settlement chronology or account drawdown. Arithmetic and existing data remain unchanged.

## Observed workflow inventory

| Workflow | Existing implementation and route | Verified boundary / gap |
| --- | --- | --- |
| Main navigation | Root workspace links `/advanced/`; advanced returns `/` | Same app, distinct UI sections. Research subtab state currently resets on page reload. |
| Screenshot/OCR exact ticket import | No image-upload/OCR route or file input in served `next_app` implementation | Missing, not credential-blocked. Do not claim screenshot import is implemented. Manual entry remains. |
| Exact slip research | `AccountSlipWorkspace` → POST `/api/account-slip-check` | Manual 2–4-leg draft with account confirmation, terms, periods, payout, bankroll/exposure inputs. No automated ticket transcription or venue acceptance verification. Stored draft is browser-local. |
| Accepted ticket evidence | `CaesarsEvidence` → `/api/execution-evidence` | Explicit authenticated manual accepted-ticket archive. Not a screenshot importer or sportsbook execution integration. |
| Root paper/actual tracking | `/api/wagers`, `/api/settle` | Actual needs ticket ID; paper separate; confirmation and payout consistency required; duplicate actual tickets blocked. Root does not implement later settlement correction revisions. |
| Advanced paper/actual tracking | `/api/wager-ledger` | Rich manual wager/parlay/currency/history fields and revisions; separate preserved ledger. No shared root totals. |
| Exposure | Root per-mode daily/open limits; advanced actual per-currency totals and browser risk preferences | Not sportsbook balances or a combined cross-ledger exposure calculation. Paper is excluded from advanced actual statistics. |
| Cashout | Root Live page gives missing-input explanation; advanced tracker supports manually recorded cashout result | No current offer/conditional joint model workflow establishing a supported hold/cashout recommendation; no cashout execution. |
| Live / 2H recheck | Advanced `LiveResearchPage`: `/api/live-board`, public lines, provider health/prices, slip audit, halftime outlook | Interactive source-backed code exists, including page-open polling and explicit provider-price action. Tests here make no live calls. Provider coverage, live clocks, participation and supported model status remain evidence-dependent. Root page deliberately stays unavailable. |
| Daily scan | Advanced Today's Board button → `/api/all-sports-report`; separate `/api/scan` research route also retained | User-initiated scan code, not a configured hosted daily scheduler. No new scan was run by this audit. |
| Alerts / line movement | Manual provider import summary computes native-identity/source-clock movement | Descriptive saved observations only. No configured background monitoring, alert delivery or notification receipt. |
| Imported provider observations | POST/GET `/api/provider-imports` | Explicit UNVERIFIED/HOLD; separate append-only observations; do not populate source board or wagers. |
| Receiving forecast/evaluation | Frozen model, saved forecast log, exact final outcome checks | Research HOLD with no profitability or real-money approval. Local tests do not establish forward performance. |

## Remaining material implementation limits

1. Advanced ledger saves replace the whole submitted collection without an optimistic version check. Concurrent browser sessions can overwrite each other's newer edits. The preserved UI now handles uncertain acknowledgements more honestly, but server conflict control remains needed before claiming reliable concurrent edits.
2. Advanced ledger server validation does not enforce every UI semantic constraint, such as confirmed settlement boolean, nonempty actual external ticket ID or duplicate sportsbook/external ticket references. Existing history is client supplied, not a server-owned immutable financial audit. Do not mistake its stored revision list for the root SQL audit.
3. Root settled records cannot be corrected through its public mutation interface; it rejects already-settled changes. Neither view should silently import the other's records as a workaround.
4. Screenshot import, exact screenshot provenance, a complete live cashout comparison, contract connectors, source-backed alert transport and cross-ledger reconciliation remain separate delivery work rather than functioning hosted features.

## Checks run

`python3 -m unittest next_app.tests.test_workflow_parity -v` using bundled Python 3.12: **6 passed**.

Four tests exercise real local HTTP with authentication/token headers and isolated databases: paper/actual identity, duplicate tickets, settlement confirmation, mode-separated results, demo/import/verified-board isolation and rejection of financial actions. Two source-level checks protect the displayed ledger boundaries and save-confirmation guard. Those two are not interactive browser tests. Existing broader app and browser checks remain the coordinator's acceptance responsibility.

## Browser acceptance added

`next_app/tests/browser_check.py` now checks independent-model navigation and hash-route reload at desktop/mobile sizes. It also intercepts only the synthetic research ledger API to exercise actual React behavior: sign-in, paper draft entry, a 503 save acknowledgement, retained draft, disabled retry, no automatic POST retry, explicit reload, successful save, cleared draft, one saved paper row and `#wagers` reload persistence. The intercepted ledger never writes to a hosted account. Syntax compilation passed; execution/build results must be recorded by the coordinator before calling this browser-verified.

The browser scenario exposed a compatibility issue: the UI expects `auth.signIn()` to return `{user}`, while the local compatibility client returned a bare user. The coordinator owns that shared-client correction. No conclusion about full parity with either hosted deployment follows from these local scenarios; the hosted builds, account-specific records and external services require separately observed read-only verification.


## Newer actual hosted source recovery — version 1792966364427

The recovered newer host WagerTracker and shared `ledgerInput`, `ledgerOwner`, `ledgerClientState` are now reused. They add captured-owner checks, load generation fencing, stronger financial/date/history input validation and a client capability for immutable pending requests and explicit reconciliation. The actual recovered backend remains legacy list/update storage: it does **not** advertise `revision-receipt-v1`, and does **not** implement compare-and-swap revisions or reconciliation receipts. Its optional client protocol branch therefore stays dormant. The active fallback preserves draft, verifies the save count and captured owner, disables edits after unknown outcomes and requires reload. No revision/concurrency/reconciliation guarantee is claimed. Whole-collection concurrent overwrite risk remains.

The port retains separate-ledger banners and placed-order drawdown disclosure. Shared pending-state recovery is tested as a local capability only, not as an activated server integration. Four new `tests/parity/ledger.test.mjs` tests passed, including the real compatibility SQLite backend, isolated owner reads, rejected malformed saves and explicit absence of a server protocol. Run with `node --test tests/parity/ledger.test.mjs` from the research runtime. Frozen models were not changed.

Coordinator verification: SDK auth wrapper repaired from current official auth
reference. Direct model/hash navigation, owner-bound ledger/SGO routes and missing
SGO credentials behavior integrated. Local production build and three runtime
checks pass; final CI browser scenarios must run against the exact release tree.
No screenshot OCR was found or added, and no automatic cashout/execution or alert
transport is claimed. Source recovery covers 29 selected complete files out of the
current deployment's inventory; full application/vendor parity remains unestablished.
