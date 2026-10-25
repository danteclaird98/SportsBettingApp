# Recovered decisions and migration status

## Current migration

The complete EdgeBoard source suite has now been vendored under `research_runtime/` and built against a local compatibility layer: all 73 API routes and original React workspaces are available at `/advanced/`. Model scoring, historical runners, provider adapters, account-slip auditing, public discovery and protected ledgers now have a standalone runtime. External calls remain dependent on credentials, network access and source response quality. Local owner sessions replace hosted authentication; this is not a multi-user deployment. The table below records the initial new-interface inventory; entries marked pending describe the new interface rather than availability in the full migrated research suite.


Source priority: SportsBettingApp's canonical EdgeOdds/research contracts; EdgeBoard's current product and corrected model decisions; edgeboard-appdeploy's earlier snapshot. Other repositories supply reference designs, not authorization to start external services. No previous chat history beyond this thread was available; this inventory is reconstructed from repository source and documentation.

| Recovered decision / capability | New standalone app | Recovered implementation |
|---|---|---|
| Today's board, simple top-level workspaces | Implemented with a new responsive layout | EdgeBoard/src/App.tsx, DailyDashboard.tsx |
| NFL, NBA, MLB, NHL | Filters and canonical pregame quote support | SportsBettingApp/docs/EDGEODDS_ARCHITECTURE.md |
| Exact event / selection / line / period / settlement identity | Reuses existing EdgeOdds contract | SportsBettingApp/edgeodds/integrations/edgeboard.py |
| Immutable provenance and quote history | Reuses EdgeOdds storage; evidence visible per quote | SportsBettingApp/edgeodds/ingestion.py |
| Freshness and outage disclosure | Preserved contract reasons; no fallback to demo | SportsBettingApp/edgeodds/read_api.py |
| Missing probability / EV stays unknown | Implemented | SportsBettingApp/edgeboard/core.py; EdgeBoard/backend/researchControls.ts |
| No unsupported parlay probability multiplication | Implemented in research slip | EdgeBoard/backend/parlayAudit.ts |
| Manual paper / actual tracking and bankroll limits | Implemented with SQLite persistence and immutable audit | EdgeBoard/src/WagerTracker.tsx |
| Export and evidence-based research reporting | JSON workspace export implemented | alexbet-sharp-bot/src/utils/export-handler.js; EdgeBoard/backend/assistantReport.ts |
| Corrected receiving60 limitations and retained negative yards | Frozen report carried forward; scoring/training remain in source | EdgeBoard/backend/correctedReceiving*; research/receiving60 |
| NFL / MLB baseline, halftime and receptions diagnostics | Five inspectable frozen reports | EdgeBoard/backend/*Report.json, *Validation.json |
| KYM / Underdog contests, alternate lines, props, Caesars | Pending standalone adapter migration and exact terms verification | EdgeBoard/backend/kym-related gameLines.ts, freeUnderdog.ts, verifyProp.ts, caesarsFeed.ts |
| Account slip import and acceptance verification | Research slip inspection implemented; import and account evidence workflows pending | EdgeBoard/src/AccountSlipWorkspace.tsx; backend/accountSlipAudit.ts |
| Live / 2H / cashout research | Workspace and explicit input blockers; live ingestion/scoring pending | EdgeBoard/backend/liveResearch.ts, halftimeOutlook.ts |
| NHL shots / league backtest, NFL prop calibration, player matchup tools | Original source retained; runner migration pending | EdgeBoard/src and backend research modules |
| Exact-market closing line value | Existing matching policies retained in core; new UI calculation pending verified close data | SportsBettingApp/edgeodds/evaluation; EdgeBoard/backend/quoteArchive.ts |
| Point-in-time model evaluation and prediction ledger | Original evaluation code retained; no invented live approval | SportsBettingApp/edgeboard; EdgeBoard/backend/predictionLedger.ts |
| Free game-market discovery and all-sports reports | Pending hosted-runtime adapter migration; not presented as a successful empty scan | EdgeBoard/backend/freeGameOdds.ts, allSportsReport.ts |
| Polling, line movement and notification delivery | Reference reviewed; not activated | live-odds-tracker |
| SportsGameOdds SDK | Cloned and reviewed; no configured provider integration | sports-odds-api-python |
| Historical odds collection | Cloned and reviewed; no scraper automatically run | OddsHarvester |
| Telegram bot, tiers, billing and AI suggestions | Optional reference integrations; not activated | alexbet-sharp-bot |
| Multi-user auth and protected research ledger | Local single-user scope; production auth migration pending | EdgeBoard/backend/index.ts and AppDeploy runtime |
| Automatic betting, account login, unsupported live markets | Disabled | SportsBettingApp/docs/EDGEODDS_ARCHITECTURE.md |

The new app's `Data & integrations` workspace discloses these gaps. Code recovery, endpoint implementation, source freshness, model calibration, executable price evidence and deployment are separate milestones.
