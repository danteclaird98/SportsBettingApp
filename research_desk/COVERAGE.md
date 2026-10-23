# Verified coverage status — 2026-10-04

**Live-verified operational sport/league/book/market combinations in this candidate: 0.** No provider key, account price verification, evaluated model or game-state feed was available. Synthetic test fixtures are not operational coverage.

| Integration | Implemented | Locally tested | Live verified | Limitation |
|---|---|---|---|---|
| The Odds API v4 sport catalog | Server-side adapter; dynamic keys and active/outright flags | Injected synthetic transport; identifier/flag handling | No | Authorized key needed; catalog membership is not coverage |
| Sportsbooks | Exact provider book key/name retained; configurable regions | Synthetic normalization and duplicate-book counting | None | No account access, book terms or executable availability verified |
| Schedules/event catalog | Provider event/start identifiers and title | Response identity validation and discovery queue | No | No postponement/result reconciliation |
| Pregame odds | Featured and exact event market retrieval | Snapshot normalization, atomic import and exclusion tests | No | Rules/status/availability remain unknown |
| Live odds observations | Started-event quotes identified as live | Timestamp/order/fail-closed tests | No | No aligned score/clock/possession feed; no eligible live research |
| Historical data | User-supplied binary prediction audit | Chronology, leakage and execution price tests | No | No historical feed adapter or dataset |
| ESPN/deployed app integrations | Existing website only, source unavailable | Not inspected in this source package | Not verified | No copied/reimplemented integration is claimed |
| Bookmaker imports/execution | Generic manual records only; execution denied | Ledger/auth/duplicates/corrections | No | No bookmaker connectors or submission logic |

## Market families

| Family | Quote/tracking schema | Provider normalization/retrieval implementation | Model/rules/availability |
|---|---|---|---|
| Two-way moneyline | Implemented | h2h, draw_no_bet; complete-price benchmark where appropriate | Unavailable/unverified |
| Three-way moneyline | Implemented | h2h with draw; explicit h2h_3_way (event retrieval) | Unavailable/unverified |
| Standard / alternate spreads | Implemented | Exact point; complementary-point benchmark only | Unavailable/unverified |
| Game / alternate totals | Implemented | Exact point and Over/Under pairing | Unavailable/unverified |
| Team totals | Implemented | Exact team description, point and market key | Unavailable/unverified |
| Player performance props | Implemented | Exact metric/participant/point; complete Over/Under benchmark only | No opportunity/participation distribution |
| Team / game event props | Implemented | Unknown keys retained as exact generic contracts; team props can be manually entered | No event-probability model or verified rules |
| Halves / quarters / periods / innings / sets | Implemented | Exact upstream segment key retained, including s1/s2 | No sport-specific state/rules/model verification |
| Futures / outrights | Implemented | Priced field retained without incomplete-field margin removal | No field completeness, settlement-horizon or outcome model |
| Parlays / same-game combinations | Leg tracking implemented | No verified priced-combination adapter | No joint probability; no independence assumption |
| Lay/exchange liability products | Not supported | Explicitly skipped with reason | Requires liability and market-fee adapter |
| Other upstream keys | Exact generic import supported | Preserved, rules unverified | Schema acceptance is not evaluated or operational support |

There are 14 generic market families. This is not a statement that every sport, book or provider supplies each one.

## Dynamic matrix

The Coverage interface/API combines:

1. Designed generic market schema rows, all marked not live verified.
2. Provider catalog rows (`catalog_only`) naming actual returned sport/league keys.
3. Recently seen market-key/book rows (`recently_seen_key`). They have not necessarily returned prices.
4. Imported/observed quote dimensions: sport, league, provider, book, exact market key/family, pregame/live scope and timestamps.

Direct successful HTTP odds retrieval may set `source_observed=true`; it does not set `live_research_verified=true`. Manual files and injected transports remain `imported_unverified`. Rules, account availability, historical coverage and model limitations remain visible. No historical row is inferred from present-day quotes.

The breadth-first scan covers the returned active catalog in chosen regions without selecting favourite sports. It retrieves featured/outright markets and then expands current events into recently seen keys and exact event odds. Continue the pending queue to finish a cycle. Recently seen keys may miss supported but unopened markets; empty responses are not claims that an entire market is unsupported. The UI also permits targeted keys for additional supported markets.

Primary specifications checked during implementation:

- [The Odds API v4 documentation](https://the-odds-api.com/liveapi/guides/v4/)
- [The Odds API market keys](https://the-odds-api.com/sports-odds-data/betting-markets.html)

Provider documentation establishes route/schema expectations; successful live retrieval and sports/book/rule verification still need to be performed with the authorized subscription.
