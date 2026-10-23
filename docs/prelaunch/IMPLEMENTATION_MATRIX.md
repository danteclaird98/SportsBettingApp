# Pre-launch fix status

Target: danteclaird98/SportsBettingApp, branch codex/prelaunch-hardening, baseline d564f027b9a9db8e64d67c5ba7e21ec583fbf65d. Historical candidate directories are preserved. research_desk is the recovered, runnable version-2 application; edgeodds is the repository's separate foundation library. Neither is claimed to be the currently deployed public application.

| Fix | Implemented and locally checked | Remaining boundary |
|---|---|---|
| 1. Recover complete source | Repository cloned and compared; recovered app includes provider module, dashboard, tests and launch command | Public deployment source/version is not established |
| 2. Identity | Source/league-scoped IDs, explicit aliases/remaps, dated-event separation, postponement/cancellation invalidation and explicit neutral-site flags | Real mappings require authoritative provider/schedule evidence |
| 3. Snapshot uniqueness | Database-enforced economic snapshot keys survive retrieval changes/restarts; conflicts retained; legacy IDs/history retained | Legacy duplicates remain historical evidence |
| 4. Price validation | Boolean/nonfinite/invalid units rejected, explicit fractional math and a documented local price ceiling | Ceiling is conservative; actual provider plausibility needs operational calibration |
| 5. Live identity | Sport, league, event start, live status, state ID/period, alignment and latency gate comparability | No verified live state connector supplied |
| 6. Transactions | Atomic batches/audit/dedupe keys, transaction-held wager limits/revisions, cross-process regression tests and consistent board read snapshots | Larger production load and backup/restore need deployment testing |
| 7. Recovery | Timeouts, 429/5xx/network cooldowns, persisted scan queue, three-attempt bound, inspectable exhausted failures and redacted health | Real provider credentials, quota and network smoke test unavailable; no background scheduler claimed |
| 8. Queries | Indexed source-time latest/history, bounded pages, cross-page best-price context, grouped board calculations and UI Load more | Aggregate reports still read the full ledger; offset pages are not frozen exports |
| 9. Security | Loopback origin/host policy, token isolation, strict JSON, bounded handlers/body/rate, text-only rendering, manual trust downgrade and safe errors | Public TLS/session/secret integration and external CVE/penetration review remain open |
| 10. Tests/docs | Compatible hashed evaluation CLI, leakage checks, regressions, first-run launcher, API/runbook/security docs and CI browser gate | Browser rerun blocked locally by failed Chromium download; live profitability unestablished |

Release level: local tested candidate. Public launch remains blocked by the explicitly listed integration and verification dependencies. No production database or deployment was changed; no wagers are submitted.
