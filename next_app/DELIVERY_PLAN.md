# Delivery plan and acceptance criteria

This plan follows the current single-owner receiving60 research workflow. Your
app has its own API key; no external odds provider is selected. A working app,
trusted data and validated predictions are separate milestones.

## 1. Reliable Render operation

- [x] Require the built research runtime and all app secrets in Render startup.
- [x] Wait for the installed artifact and workspace storage to become ready.
- [x] Expose minimal `/healthz` status and authenticated diagnostic detail.
- [x] Stop the workspace if its research process exits, allowing host recovery.
- [x] Configure Render to use an HTTP readiness check rather than an open port.
- [ ] Verify the deployed HTTPS URL in your Render account.

Acceptance: a healthy full app returns 200 from `/healthz`; a missing or failed
model/storage component produces 503. No secrets or research data are public.
An open listener alone is insufficient. Readiness does not establish live data
availability or model approval.

## 2. Recoverable saved data

- [x] Add online SQLite snapshots, including committed WAL content.
- [x] Record SHA-256 checksums and SQLite integrity verification.
- [x] Restore only into a new directory, preserving existing data.
- [x] Exercise receipt recovery against disposable data.
- [ ] Configure an off-host backup destination and retention in your account.
- [ ] Test a restore using a backup from the deployed persistent disk.

Acceptance: original receipts and audits survive a snapshot/restore; modified
backup files fail verification. A backup kept only on the same Render disk is
not independent disaster recovery. The tool snapshots each database separately;
there is no cross-database transaction guarantee.

## 3. Repeatable regression checks

- [x] Add GitHub Actions for backend, model, storage, browser and image checks.
- [x] Use test isolation settings that execute and report the model assertions.
- [x] Record the missing real-data cohort as skipped, not validated.
- [ ] Observe the new workflow's result on GitHub after pushing.

Acceptance: a failed assertion fails CI. Both desktop and mobile research flows
must score, abstain, save, reload and download matching request/response pairs.

## 4. Independently sourced player history

- [ ] Choose a permitted player-results and schedule source (no The Odds API).
- [ ] Verify stable player/game IDs, regular-season scope and final-result status.
- [ ] Capture raw source responses, source URLs/IDs, retrieval times and hashes.
- [ ] Record the first actual observation of each final result; never invent a
  historical publication timestamp from a game date or CSV row order.
- [ ] Match the target schedule and eligible pregame player cohort separately
  from the recorded-player-row model scope.
- [ ] Import a small real batch, reconcile it manually, then expand.

Acceptance: each input can be traced to its source and was available before its
decision time. Synthetic and client-supplied labels alone cannot establish this.
Existing saved receipts remain unverified even when their storage hash matches.

## 5. Frozen forward validation

- [ ] Freeze a written protocol before collecting the evaluation cohort: model
  hash, target, eligible cohort, feature clocks, collection start/end, missing
  data handling, baseline metrics and minimum evidence needed for conclusions.
- [ ] Collect predictions before kickoff after that protocol is frozen.
- [ ] Collect final outcomes separately, preserving unresolved/missing cases.
- [ ] Evaluate against declared baselines with uncertainty and coverage counts.
- [ ] Review the result without retuning on the evaluation cohort.

Acceptance: no reuse of the consumed 2025 diagnostic as an untouched test; no
claim that the in-sample calibration selection proves improved calibration.
The current model estimates conditional recorded-player outcomes, not
participation. Keep HOLD until the separate evidence review is complete.

## Account-dependent launch sequence

1. Create/connect Render, select `codex/render-private-api` and review charges.
2. Deploy the Blueprint with its persistent disk and generated app secrets.
3. Check HTTPS, browser login, API authentication and `/healthz`.
4. Save a synthetic receipt, restart, and retrieve the original record.
5. Take a backup, copy it off-host, verify it and perform an isolated restore.
6. Only then begin the independently sourced data and forward-validation steps.

Code and local tests do not establish that these account actions have happened.
