# Remaining release gates

The software fixes are mapped in `../docs/prelaunch/IMPLEMENTATION_MATRIX.md` when used inside the repository. The local app includes a complete first-run path and its original ledger/provider/dashboard workflows. It is not a replacement deployment for the separate public EdgeBoard application.

1. Configure an authorized provider key/subscription on the intended server, select the desired books/regions and verify a real read-only request against provider timestamps, quota and identities.
2. Supply authoritative schedule and game-state connectors before claiming live comparability, plus verified settlement contracts/account-level availability before actionable price comparisons.
3. Identify the public deployment's actual source/version and integrate production authentication, TLS, secrets, monitoring and backup/restore there; the local server deliberately remains loopback-only.
4. Pass the fresh browser CI gate; local browser installation failed in this environment, so responsive rendering after these changes is not signed off.
5. Complete runtime/dependency vulnerability review and deployment load testing; the application uses only Python's standard library, which does not establish a vulnerability clearance.
6. Supply an as-of historical dataset and frozen evaluated model before producing qualifying EV research; no model or profitability claim has been established.

No unattended worker, alert delivery, real-money order connector, active live state feed or public launch is claimed. Exhausted provider scan tasks remain inspectable, and the scan can be resumed manually with a bounded request budget. Alias changes affect future imports; existing history remains immutable.
