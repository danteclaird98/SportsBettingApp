# EdgeBoard ledger review and repairs

Reviewed main27f9f53c6a3d96baca3479af866f57f4d067bf95 / PR30 head07f22a07b6c6c963d999a0608e7463eaa0057c1d. Code Review plugin diagnostics confirmed CI success on that exact head; its two annotations are runner/action deprecation notices, not application failures. Source review and isolated reproductions were performed separately by the coordinator. No private production records or deployments were touched.

## Findings reproduced before changes

- **P1 — whole-ledger replacement loses accepted concurrent edits.** Two independent saves could both report success while only the last payload remained visible. Synthetic first-save reproduction acknowledged two one-record saves and returned only record b; existing-ledger reproduction retained base,b while dropping a. The previous code listed the head and updated it without an expected revision. This was a documented existing limitation, not a newly introduced regression.
- **P2 — enum coercion accepts malformed records.** `String(w.mode/status/betType)` allowed arrays such as `["actual"]` or `["open"]` through validation. Subsequent strict comparisons could exclude actual exposure or treat an open wager as settled. The reproduction accepted arrays for all three fields; an array open-status plus true settlement confirmation also bypassed the open-state guard.

## Repairs

The local research ledger now advertises the existing client's revision-receipt-v1 protocol. A BEGIN IMMEDIATE transaction checks the expected revision, updates the existing record in place, appends a durable request receipt and audit row, and commits them together. A stale request returns conflict; a repeated request returns its historical receipt without replacing newer state. Reconciliation only reads the original receipt and never resubmits an unknown save. Request owner, ID and payload identity are bound. SQLite connections close after every operation.

Valid legacy ledger data remains at the same record ID and collection. GET reads it as revision0 without modifying its contents. Multiple legacy head records are preserved and require explicit recovery; the code does not guess a merge or delete records. The separate workspace ledger is unchanged. Both actual and paper tracking remain manual records, with no wagering/cashout/transfer executor.

New server validation requires actual strings for mode, status and betType. Malformed arrays are rejected before writes.

## API compatibility and deployment

Clients must GET /api/wager-ledger, retain owner/revision, then POST `{action:"save",owner,requestId,expectedRevision,wagers}`. After an uncertain acknowledgement, POST the same envelope with action:"reconcile". Old unversioned whole-ledger writes are rejected with a reload instruction. The already shipped research UI supports this protocol; its previously dormant recovery controls are now backed by the local server. This is a deliberate safety change for external clients, not an AppDeploy account migration. The actual hosted AppDeploy export still has its legacy backend until a separate verified deployment.

Receipts are locally append-only and atomic with the ledger, not externally immutable or venue-confirmed execution evidence. No private data is automatically merged or synchronized across apps.

## Verification

- Ten focused ledger tests passed, including two independent Node processes, stale conflicts, lost-acknowledgement recovery after a fresh module load, owner isolation, immutable request identities, forced receipt-insert rollback, preserved legacy record IDs and duplicate-legacy recovery refusal.
- Full research/parity suite:94 passed. Workspace suite:41 passed.
- Browser acceptance now commits a real isolated save, substitutes a failed acknowledgement, reloads the page and reconciles the receipt while verifying only one save POST occurred.
- Exact new-tree build/browser/container CI must complete before merge. Historical green CI is not proof for these repairs.
