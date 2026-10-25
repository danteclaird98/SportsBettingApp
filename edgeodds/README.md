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

The [architecture roadmap](../docs/EDGEODDS_ARCHITECTURE.md#roadmap) also tracks an
optional [Decisions API component](../docs/integration/DECISIONS_API.md), scoped
as an independently tested adapter within the existing agent architecture.
The component is implemented and default-off; its live trial remains pending.
Run its offline checks separately with
`python -m unittest edgeodds.tests.test_decisions_integration -v`.

1. Add deterministic team/event alias resolution with provenance.
2. Add one authorized sportsbook-odds adapter.
3. Archive the raw provider payload and its hash.
4. Normalize moneyline/spread/total into this contract.
5. Expose a read-only compatibility endpoint for EdgeBoard.
6. Compare normalized output against the existing EdgeBoard / Sports Research Desk identity and freshness rules.
