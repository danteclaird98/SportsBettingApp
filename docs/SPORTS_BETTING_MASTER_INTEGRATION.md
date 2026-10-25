# Sports Betting Master integration — October 25, 2026

EdgeBoard remains the single application in danteclaird98/SportsBettingApp.
Source: https://github.com/danteclaird98/sports-betting-master at
95d5e37a85a3faa2d7942a9c90b631a0c0471309.
Destination baseline: 12b5a585de17122b42af44b70c783bc8404a2df8.

## Implemented slice

The existing advanced Models section now includes source-backed receiving forecasts,
frozen retrospective validation, append-only saved forecast receipts and explicit
outcome evaluation. Seven routes are added to the existing authenticated research
proxy. Owner-bound history uses the existing RESEARCH_DB persistence location,
so existing volume/backup handling applies. No separate server or app was added.
The original odds gateway, receiving60 endpoint, stronger safe-integer validation,
frozen model artifacts and existing navigation remain intact.

Forecasts remain conditional research, HOLD, executionEnabled=false and no verified
positive EV. Retrospective evaluation is not prospective validation. Source reads
are explicit user operations; no scheduled scan or paid feed was enabled.

## Observed validation

Before changes: workspace 22/22 and EdgeOdds 140/140.
After changes: added source/failure/storage/evaluation tests 50/50; workspace 22/22;
model tests 13 pass, one external-data test skipped; actual loopback HTTP/runtime
checks 3/3 including owner mismatch, anonymous history denial, persisted history,
and invalid forecast HOLD. Production frontend and backend builds pass.
CI now includes the added tests. Hosted/container/browser verification of this new
slice remains pending; prior CI results do not validate this commit.

## Remaining integration

Provider response imports, movement tracking and other changed Master modules
have not been copied. They require a bridge to EdgeBoard's stronger native identity,
source-clock and immutable observation contracts; importing a quote must not grant
verification or create a wagering signal. Eight consolidated source snapshots remain
traceable in Master rather than duplicated wholesale. Existing private ledgers have
not been read, copied or migrated. No vendor credentials or regulated permissions
are implied. No deployment was performed and the current hosted app is untouched.

Render's existing blueprint remains a prepared paid service configuration, with
automatic deployment off. Creating a service/disk requires a concrete cost/account
gate. Real-money wagers, cashout acceptance, orders and transfers stay disabled.
