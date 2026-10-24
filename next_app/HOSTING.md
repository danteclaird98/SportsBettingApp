# Private single-owner hosting preparation

## Selected host: Fly.io

Use [FLY.md](FLY.md) for the current setup. Railway signup is currently paused;
check https://status.railway.com/ before attempting a new account there.

## Previous Railway configuration

[RAILWAY.md](RAILWAY.md) documents the existing alternative. The configuration uses
`railway.json`, the existing Docker image, a volume at `/var/data` and your
private app credentials. No host has been provisioned yet.

## Previous Render configuration (optional alternative)

The repository root now includes `render.yaml` and `next_app/Dockerfile`.
The Blueprint prepares one Starter Docker web service and a 1 GB persistent
disk at `/var/data`. Both compute and disk are billable; review Render's current
estimate before creating the service. Automatic redeploys are disabled.

No sports-data provider is selected or required by this Blueprint. The Odds API
is not configured. Live data remains unavailable until another source is chosen
and connected; hosting the application does not supply a sports-data feed.

1. Create a Render account at https://dashboard.render.com/ and connect GitHub.
2. Use the `codex/render-private-api` branch, which includes PR #25 and this
   deployment setup. Confirm the branch exists on GitHub before continuing.
3. In Render, create a Blueprint from `danteclaird98/SportsBettingApp`, selecting
   the branch containing these files. Review the service and disk charges
   before creating it. No sports-data key is requested.
4. Render generates `WORKSPACE_PASSWORD`. Retrieve it privately in the service's
   Environment settings. Use username `owner` and that password at the HTTPS URL.
5. Open `/advanced/` and use its local-owner sign-in. Provider-backed tools will
   show unavailable states until an authorized source has been connected.

The Blueprint uses `/healthz` for HTTP readiness. This public probe returns only
a status and verifies workspace storage readability and the installed model.
Every user-data/API route still requires workspace authentication. Detailed
checks are available at authenticated `/api/system/readiness`. See
[OPERATIONS.md](OPERATIONS.md) for backups and isolated restore tests.

### Your app's API key

Render generates a separate `WORKSPACE_API_KEY`. Retrieve it privately from
Render's Environment settings after creating the service. API clients send
`Authorization: Bearer YOUR_KEY` over HTTPS to `/api/` or `/research-api/` routes.
For example, a GET request to `/api/models` returns the frozen research catalog.
Never include the key in URLs, frontend code, screenshots or chat.

This key grants full single-owner API access, including ledger mutations and
exports. Bearer-authenticated requests do not need the browser workspace token;
cross-site POST requests remain blocked. The key does not log a browser into
the HTML interfaces. Use `owner` and `WORKSPACE_PASSWORD` for browser access.
Rotate the key by replacing it in Render and restarting/deploying the service;
the old key then stops working. There is one key, without per-client scopes or
expiry. It authenticates your application API; it does not supply external
sports data. For local operation, set a random value of at least 32 characters
in `WORKSPACE_API_KEY` before starting the server.

The container runs as an unprivileged user, with Node bound only to loopback.
Check that the mounted disk is writable by UID 10001. If startup reports a
permission error, fix disk ownership through the host's supported controls.
Do not remove password protection or change to ephemeral storage to get past
a setup error.

Official setup references: https://render.com/docs/blueprint-spec and
https://render.com/docs/disks.

The server now supports an optional HTTP Basic access gate covering the board,
advanced suite, bootstrap tokens, exports and API writes. This is one private
workspace with shared owner access; it does not create independent user accounts.
The advanced suite's local sign-in is still only an owner selector inside this gate.

## Runtime

Use Python 3.12+, Node 24+ and npm. From the repository root:

```sh
cd next_app/research_runtime
npm ci
npm run build
cd ../..
python next_app/server.py --data-dir /absolute/persistent/edgeboard-data --port 8080
```

Set `WORKSPACE_USER` and `WORKSPACE_PASSWORD` using the host's secret manager
before starting. Use a randomly generated password of at least 24 characters.
Do not commit credentials, put them in command arguments or paste them into chat.
Both values must be set together. They also protect local access when set.

Keep the default loopback listener when an HTTPS reverse proxy runs on the same
machine. Container hosts can use `--host 0.0.0.0`, which refuses to start without
the access credentials. Bind that port only to the host's private ingress and
require HTTPS at the public edge. Never expose the plain HTTP port directly.
Forward Authorization headers and impose connection limits, request timeouts
and login rate limits at the proxy. The application does not provision TLS or
provide brute-force throttling. Keep Node's port 8091 private.

Mount persistent storage at the selected data directory. It holds the workspace,
captured odds and advanced research SQLite databases. Run a single instance with
a writable volume, back up all databases using SQLite-aware backups or while
the service is stopped, and verify restore before storing actual ticket records.
The workspace database also holds explicitly saved receiving60 research receipts;
their list and individual downloads remain available without the Node scorer.
Run under an unprivileged service account and restart the entire process group
on failure. This document prepares deployment; no host has been provisioned.

## Live data

The advanced runtime already reads these server-side provider secret names:
`PARLAY_API_KEY`, `SHARPAPI_KEY`, `THE_ODDS_API_KEY`, `CLEARSPORTS_API_KEY`,
and `PUCKAPI_API_KEY`. The separate EdgeOdds capture path uses
`SPORTRADAR_API_KEY`. Configure only providers for which you have authorized
access and enable their actual API destinations in the runtime network policy.
Provider credentials alone do not establish entitlement to every market.

The main board reads captured EdgeOdds network quotes; adding an advanced-suite
provider key does not automatically populate that board. Follow the existing
EdgeOdds ingestion CLI and reviewed event bindings, then point `--odds-db` at its
database. Synthetic demo mode remains separate.

Before declaring a feed live, inspect an authenticated response for event IDs,
source timestamps, supported markets and quota status. Check it in the intended
interface. Do not infer successful live access from credential presence.

## Verification before publishing

Run `python -m unittest discover -s next_app/tests -v` and build the research
runtime. From outside the hosting network, verify HTTPS, rejection of anonymous
board/API/advanced/export requests, authorized access, blocked port 8091 and
data persistence after restart. Hosting choice and provider access are still
needed to perform these production checks.
