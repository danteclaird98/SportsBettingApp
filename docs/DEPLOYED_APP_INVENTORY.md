# Deployed EdgeBoard inventory and source recovery

Observed October 25, 2026, approximately 3:14–3:20 PM America/Los_Angeles. Repository audit baseline: `0de472f`. This read-only inventory did not deploy, restore a version, change accounts, run provider scans, inspect private ledgers, or access secret values.

## Current observed applications

| Application | URL | Connector access and status | Version evidence |
| --- | --- | --- | --- |
| EdgeBoard research | https://edgeboard-research-ai9jat.v2.appdeploy.ai/ | Both authorized AppDeploy links list it as deployed; both status calls return `ready` | Both list/status responses pin `1792966364427`, label v17, October 25 at 3:12:44 PM Pacific |
| Original shared EdgeBoard | https://edgeboard-kshzox.v2.appdeploy.ai/ | Not listed by either connection; both status and versions calls return `Unauthorized` | No current version retrievable through these connections; historical source references are not current deployment evidence |

Both connections returned the same five-app inventory, including exactly one sports/EdgeBoard app. Neither response contained a continuation token, so there was no remaining page to fetch. The other four apps are unrelated projects and were not inspected further. An unauthorized status response contains an internal `failed` field; this does **not** establish that the original deployment itself has failed. It establishes access denial.

No additional deployed EdgeBoard URL was found in the audited repository hosting documents. Example Fly URL placeholders and generic Railway/Render documentation links are not actual deployments. The Render blueprint remains preparation rather than an observed hosted release. The coordinator separately owns browser reachability/workflow evidence; connector `ready` alone does not prove feature parity or workflow correctness.

## Source recovered for comparison

Authorized source reads were explicitly pinned to valid version `1792966364427`, rather than defaulting to the last attempted snapshot. The source inventory returns 40 `src/` paths, 78 `backend/` paths, 10 `shared/` paths and one `tests/tests.json` path, with no continuation tokens for these directory inventories. A preliminary exact-file glob returned a terminal empty second page; no source content was inferred from that result.

A selected 29-file comparison closure is recovered at `/private/tmp/edgeboard-hosted-current-20261025/`. `SOURCE_MANIFEST.json` there records each exact UTF-8 source file's SHA-256, byte count and comparison result. All selected reads reported at most 2,000 total lines and were read completely, without truncation. This is a partial source recovery, not a full repository export. It includes application navigation, daily dashboard, exact-slip workspace, wager UI and ledger helpers, backend router, all-sports report, independent reception model/validation artifacts, prop verification, SportsGameOdds modules and all shared modules. These are code/model artifacts; no private database, account records or credentials were exported.

Source-only inspection found material differences requiring integration review:

- Hosted wager UI imports new ledger client-state/input/owner helpers. Its backend ledger and owner checks need to be preserved when adapting to local runtime authentication and persistence.
- Hosted SportsGameOdds module/core/store files are absent from the initial destination baseline. Their existence does not prove licensed-provider access or authorize a live request.
- Independent reception artifacts, features, prop evidence and verification differ from the initial destination baseline. Preserve this newer evidence and compare exact behavior rather than assuming a same-named module is equivalent.
- The daily dashboard, daily report/status helpers, shared prop evidence, receiving blockers, SGO owner helper and all-sports report match destination source bytes. Those matches are source parity only.
- Navigation, exact-slip/wager UI, router and receiving evaluation report differ. Some differences can reflect required runtime adaptations; do not overwrite stronger gateway, private authentication, database persistence or receiving-model safeguards blindly.

## Next objective gates

1. Compare the recovered closure with the canonical EdgeBoard runtime and integrate justified newer behavior in that existing app. Record deliberate compatibility adaptations and preserved destination-only safeguards.
2. Run deterministic, isolated API, ownership, ledger replay, model and browser tests for the combined tree. Source hashes and a successful deployment-status call do not substitute for those results.
3. Test current hosted workflows read-only first. Any hosted change needs a concrete reviewed release and separate authorization consistent with the chosen hosting account. Never overwrite the original shared app to bypass its access failure.
4. If work on the original `edgeboard-kshzox` app is necessary, its owner must grant authorized access or connect the owning account. Repeated retries against these same unauthorized connections do not resolve ownership.

## Tool limitations encountered

The connector rejects status `limit=0` (minimum 1); the corrected status reads used limit 1 and a future error filter to avoid retrieving historical application logs. Source `limit=10000` is rejected (maximum 2000); subsequent source reads used 2000 and checked total lines. Rejected calls produced no source recovery or status verification and are not counted as successes. No application error-log content was needed for this inventory.

## Recovered-file hashes

| Path | SHA-256 | Initial comparison |
| --- | --- | --- |
| `backend/allSportsReport.ts` | `89a47511afce8ab2fc971bc7b4dd8f4d1d3700d1e3b122de303c95615266753f` | SAME |
| `backend/independentReceptionArtifact.json` | `2cef8576a3dd9ba5c53537844af82263d1e6bcfbef24565497ef3ee517ce91e4` | DIFF |
| `backend/independentReceptionValidation.json` | `c86e33977fd1950b2c0bfa2993bb86eadd3f9a5e5c2308794f25421bd934e9e4` | DIFF |
| `backend/independentReceptions.ts` | `97f84af96ce94778c552a4a63bcdc9eb82eef5d9afa9409f210617ae032c03db` | DIFF |
| `backend/index.ts` | `acdddd94b6662d8bfdd4fb4b2c2b37a04a8fd8d2c039d3b406b8f381a0ca243d` | DIFF |
| `backend/propEventEvidence.ts` | `e29c79eb202a7ae3b9d4cbd6bdba100851c657b2616fb7ea4260107a213b02ba` | DIFF |
| `backend/receptionFeatures.ts` | `3a606a7df1657d23f82d7a9e3c2abb7a7392f40feba1104cca1faa19f2dc91b1` | DIFF |
| `backend/sportsGameOdds.ts` | `d76b4cb1505be46be859eec46c7136edc2c5fa78128643c3508812849d1c1f94` | NEW |
| `backend/sportsGameOddsCore.ts` | `81f152ce1589b9dbc799d3e3d32fa14b6c41d7c5ad27c3ae531ada86d3eb066d` | NEW |
| `backend/sportsGameOddsStore.ts` | `905b58637a777030e6207a853dd5bc4440a97266d0f41ed8a017f5dba055052f` | NEW |
| `backend/verifyProp.ts` | `36ea346e156e3fa5034965b47ebc16964b0569b46927c52f68e90acf7540b138` | DIFF |
| `backend/wagerLedger.ts` | `ccb99e17d1feb6aea2b31644683b65cf15c1c99dc77338bef085a24ac002d9ae` | DIFF |
| `shared/accountSlip.ts` | `bf8fb232f7f8f03d4b437cc1aeeb1a087e836a4cf405ae70e5bf43d5d506d9ab` | DIFF |
| `shared/dailyReport.ts` | `89bb9ae6281de2a06cdfe7944d17bf8afb7d1ce242e7f2973b74273c837d1508` | SAME |
| `shared/dailyScanStatus.ts` | `07d940dd04feb3cff3f047b7e174ca42ca6913603638035805a32101cf79e41d` | SAME |
| `shared/ledgerClientState.ts` | `74632164c6f0d2ee8ca1193b61d0425786c588654f2e148a29e20f49beacd19e` | NEW |
| `shared/ledgerInput.ts` | `9415ccffd38003f62d759068bcb227bf4e65c09da06f5fc8a48ce184ac5fd59d` | NEW |
| `shared/ledgerOwner.ts` | `8f0075adb34e32f2b5a3416fb01b714050dc8ab01d03db30513b47d812c48e7c` | NEW |
| `shared/propEvidence.ts` | `21137f29dbf55e489489752e74f5dcf5a1a99998a9c2b9ac25046d07c0b6d053` | SAME |
| `shared/receivingBlockers.ts` | `ca2b0719037e78a8f29753138c17bd2f9e23299f7d399827007dbc620409aa10` | SAME |
| `shared/receivingEvaluationReport.ts` | `388a49f9d37186eacf50e63425a1671f0d9afc2faa2964d4ddd6cd0cb6223c7c` | DIFF |
| `shared/sgoOwner.ts` | `b7e18c9d07d209d3ac14472eb4ff6c9a0cb7056e16e8eb2d777b2ff5b9d6417e` | SAME |
| `src/AccountSlipWorkspace.tsx` | `694b9595a9870de11422200f61e2c4a8cfe2b96201f5a6284c32a831386a6711` | DIFF |
| `src/App.tsx` | `f2d9d7bcb7731cea31414d6e350d21d5b09cf338925a22c14d901da776e528a9` | DIFF |
| `src/DailyDashboard.tsx` | `e40706734e710b773906b66af635dae0587b0191828e9bab39f2f53ce634646e` | SAME |
| `src/PropVerification.css` | `2bf6ec1685050b8a544f41f926d20ff02df9a0091dfafbba8dc14e6c53f6c078` | SAME |
| `src/PropVerification.tsx` | `e920a365cda35e560eb93e946749b3e1da02ed25a5e7385cb3bd7b6cb5b51254` | DIFF |
| `src/WagerTracker.tsx` | `71fc48c07f62a0c8fd867c3bff48823862baeb17d198a9457d88c2d4a00cb4c3` | DIFF |
| `tests/tests.json` | `e8eaae4d1fa36aa5f797041082d4189ed73cba3f32fba95a6419fcc8ecdce168` | DIFF |

## Completed source recovery

Coordinator subsequently recovered every one of the128 src/backend/shared files at the same pinned valid release, with no read errors. The selected29-file boundary above describes the initial audit stage. Exact full file hashes are now in HOSTED_SOURCE_MANIFEST.json. This completes source recovery for those directories, not hosted workflow/provider/record verification. Both public URLs rendered during read-only browser checks; no scan, account sign-in, ledger access or provider request was triggered.
