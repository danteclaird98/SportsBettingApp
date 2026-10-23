# EdgeOdds

EdgeOdds is the normalized sportsbook market-data layer for EdgeBoard / MarketEdge OS.

## v0.1 foundation

This branch establishes the data contract before adding live providers.

Implemented:
- canonical event and market identity primitives;
- moneyline, spread, and total market types;
- provider-native IDs kept alongside canonical IDs;
- decimal price normalization boundary;
- provider update time kept separate from retrieval time;
- explicit market status and connector-health states;
- freshness gating that refuses to substitute retrieval time for a missing provider timestamp;
- append-only SQLite quote snapshots with exact-repeat deduplication;
- provider adapter protocol;
- standard-library regression tests.

Not implemented yet:
- live sportsbook adapters;
- player props;
- event/entity matching;
- official schedule/roster/injury adapters;
- consensus/no-vig service;
- EdgeBoard API compatibility routes;
- deployment;
- betting, account login, or order execution.

## Design rule

A connector outage is data unavailability, not evidence that there are no positive-EV opportunities.
Unknown fields stay unknown. Provider names and display labels never establish market equivalence by themselves.

## Run tests

From the repository root:

```bash
python -m unittest discover -s edgeodds/tests -v
```

## Next vertical slice

1. Add deterministic team/event alias resolution with provenance.
2. Add one authorized sportsbook-odds adapter.
3. Archive the raw provider payload and its hash.
4. Normalize moneyline/spread/total into this contract.
5. Expose a read-only compatibility endpoint for EdgeBoard.
6. Compare normalized output against the existing EdgeBoard / Sports Research Desk identity and freshness rules.

## Pre-launch repairs

Snapshot dedupe now uses source-observed economic content rather than retrieval time or an envelope hash. Batches commit atomically, connections close, and migrations backfill semantic keys/indexes while retaining old snapshot IDs and legacy duplicate history. `latest()` now returns current source-time snapshots per provider/book/contract, retaining simultaneous conflicts and market halts; use `history()` for the old recent-history behavior. Both support event/book filtering and bounded limit/offset, with a maximum of 500 rows per call.

Explicit neutral-site flags permit swapped participant orientation only when both the provider event and canonical event declare a neutral site. Dated aliases require an as-of time. This foundation still has no live provider adapter registered or independent HTTP server. The runnable user-isolated dashboard/provider/API continuation is in `../research_desk/`; its store remains separate by design. See `../docs/prelaunch/IMPLEMENTATION_MATRIX.md` for release gates.
