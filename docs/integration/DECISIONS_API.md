# Decisions API integration roadmap

Status: **implemented and offline-tested; default-off; live trial pending**. This is a small optional
component within [E4a of the EdgeOdds roadmap](../EDGEODDS_ARCHITECTURE.md#e4a--decisions-api-component-optional).

## Component boundary

The existing orchestrator owns delegation and release decisions; specialist
workers retain the lanes in [the parallel-agent operating model](../EDGEODDS_PARALLEL_AGENTS.md).
EdgeOdds continues to own canonical identity, provenance, quote storage and its
read-only API. EdgeBoard continues to own forecasting and eligibility checks.
Decisions API adds one adapter; it does not replace this architecture or become
a required dependency for ingestion, existing agents or the EdgeBoard v1 route.

Start with one advisory evidence-readiness check on a frozen canonical research
packet. Existing deterministic identity, settlement and freshness checks remain
authoritative. An API response cannot supply missing source evidence, change
canonical records, approve a connector/model or authorize a wager.

Implementation ownership: the `edgeboard-integration` lane, reviewed by
`reliability-security`, with integration controlled by the existing orchestrator.
Files are `edgeodds/integrations/decisions.py` and the separately runnable
`edgeodds/tests/test_decisions_integration.py`. No canonical-schema or
agent-framework migration is part of this component.

## Small executable tasks

| ID | Task | Independently reviewable acceptance check |
| --- | --- | --- |
| D1 | Establish the actual API contract | Identify provider, official documentation URL/version, access requirements, supported request/response fields, timeout/error semantics, rate limits and cost. Archive a sanitized documented example. Record unsupported capabilities explicitly; do not invent an endpoint or assume SDK compatibility. |
| D2 | Define the narrow adapter and fixtures | Specify one versioned local input/output contract and synthetic fixtures. Input binds request ID, packet hash, decision time and exact market identity. Advisory output binds the same request/packet, API version, outcome and evidence references. Malformed, mismatched or unsupported results are unavailable, not approval. Keep vendor fields inside the adapter; leave `edgeodds.edgeboard.v1` unchanged. |
| D3 | Implement and test the adapter offline | Inject transport and clock; use a fake transport with no credentials or network. Separately run `python -m unittest edgeodds.tests.test_decisions_integration -v` once implemented. Verify valid mapping, missing/malformed fields, wrong packet/request identity, stale evidence, timeout, auth denial, rate limiting, duplicate responses and bounded retries. No automatic retry of an uncertain submission without documented replay/idempotency semantics. |
| D4 | Prove compatibility and failure isolation | With the feature disabled, existing outputs remain unchanged and no API request occurs. With it enabled, outages and invalid responses produce an explicit unavailable advisory result while the existing workflow continues. API agreement never overrides a failed deterministic gate. Run the full EdgeOdds regression suite and verify ingestion, worker contracts and EdgeBoard v1 exports remain compatible. |
| D5 | Run a bounded shadow trial and decide activation | After D1–D4, use an explicitly enabled trial with a fixed request/time/cost budget, pinned API/adapter versions, recorded input hashes and predeclared success criteria. Compare with the existing workflow for correctness, missing-evidence handling, disagreement, latency and observed cost. Test the disable switch; release only this component if the evidence justifies it. |

D1 precedes D2; D3 follows the agreed contract; D4 and D5 gate activation.
The component is default-off. E4 and existing agent work can ship independently
if API access, evidence or usefulness is insufficient.

## Integration and rollout contract

The intended flow is: existing orchestrator → optional adapter → validated
advisory result → existing orchestrator. The adapter receives the smallest
necessary immutable packet; provider credentials, user tokens and private wager
ledgers are excluded. Credentials for the Decisions API, if required, stay in
server-side configuration. Logs retain correlation IDs, packet hashes, versions,
timings and error categories without exposing secrets.

Define the outcome vocabulary during D2, keeping API unavailability distinct
from an evidence-based negative decision. Preserve original source timestamps
and evidence references; an API response is not an independent odds source or
a replacement for model validation. Record disagreements for review rather than
using agent voting to turn an unsupported result into eligibility.

Shadow mode does not change displayed recommendations, quote persistence or
existing agent routing. Turning the component off restores the existing path
without a data migration. Offline tests establish adapter behavior; live API
compatibility and production benefit require separate trial evidence.

## Implementation and verification

D1 documentation discovery is complete: the provider is OpenAI. The reviewed
[contract evidence](DECISIONS_API_CONTRACT.md) records the official endpoint,
request/response fields, authentication, current pricing and unknowns. Project
entitlement and live behavior remain unverified. The supported `gpt-6-luna`
name is an alias, not an immutable dated snapshot.

D2–D3 are implemented with standard-library Python. `EvidencePacket` contains
one canonical quote, decision time and explicit identity/rules flags. Its
canonical SHA-256 binds the immutable market, source and timestamp fields.
`DecisionAdvisor.evaluate(packet, request_id=...)` asks one choice question.
The returned question name binds the local request and packet; the API does
not natively echo packet hashes or produce source citations. `evidence_refs`
are locally derived archive references, not model-generated evidence.

Results distinguish `DISABLED`, `ADVISORY` and `UNAVAILABLE`. Advisory choices
are `SUFFICIENT`, `INSUFFICIENT` or `UNCERTAIN`. `deterministic_ready` describes
only existing local identity/rules/freshness checks; neither it nor the choice
is betting eligibility. Receipts include local adapter/schema versions and the
observed model for valid answers. Classification confidence is not a sports
hit probability or calibrated proof of readiness.

The component defaults to disabled, has a one-call default instance budget,
and issues no automatic retries. Request/response limits are 16 KiB/64 KiB.
The HTTP transport uses a fixed OpenAI HTTPS origin, does not follow redirects,
and redacts credentials and provider error bodies. Clock failures, malformed
answers, refusals, missing/future/stale/post-decision evidence and expired
replays fail closed. The default timeout is five seconds of socket IO;
late completions are rejected, but blocking inference cannot be cancelled or
proven unbilled by this component.

Request-ID/hash binding and cached uncertain outcomes apply to one advisor
instance only. They are not durable or cross-process idempotency. A restart
must not be treated as permission to retry an uncertain billed request.
Shadow trials must retain operator receipts across runs and use new evidence
only under their declared budget.

D4 offline compatibility checks pass: 18 component tests and all 158 EdgeOdds
tests pass. Coverage includes concurrent duplicate suppression, mismatched
requests, expiry during inference/replay, clock failure, no-lookahead,
malformed distributions/usage, failure isolation, redirect denial and size
bounds. The existing EdgeBoard v1 contract and agent-routing code are unchanged.
These are synthetic correctness checks, not evidence of model usefulness or
live API compatibility.

D5 remains pending: secure API-key target selection has not returned a confirmed
organization/project, no credential has been created or saved, and no live
request or paid trial has run. No activation or live EdgeBoard deployment was
made. A bounded trial must establish access, actual latency/cost and benefit
before runtime wiring or promotion.

Run the component independently:

```sh
python -m unittest edgeodds.tests.test_decisions_integration -v
python -m unittest discover -s edgeodds/tests -v
```

The adapter is a callable library component, not an installed service. The
existing orchestrator may invoke it explicitly in shadow work after D5 setup;
no existing request path imports or enables it automatically.
