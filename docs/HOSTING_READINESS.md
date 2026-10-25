# EdgeBoard hosting readiness

Checked October 25, 2026 against `a010941` plus the current agent-fix working tree. This is a deployment handoff, not a record of a deployment. The existing AppDeploy application has not been replaced. Financial execution remains disabled.

## Prepared release

Use the existing `danteclaird98/SportsBettingApp` repository and its checked release commit. The root `render.yaml` already defines one service named `edgeboard`, built from `next_app/Dockerfile` with repository-root context. It runs both the Python workspace and the preserved Node research tools behind one private HTTP entry point. Do not create another application repository or deploy the reference Sports Betting Master server.

| Setting | Prepared value | Reason |
| --- | --- | --- |
| Runtime | Docker, one instance | Existing Python/Node application and local SQLite stores |
| Compute | `starter` (current schema also calls this `0.5c-512mb`) | Small initial private deployment; memory capacity still needs hosted measurement |
| Disk | 1 GB at `/var/data` | Workspace, research/forward receipts, and odds evidence persistence |
| Public readiness | `/healthz` | Minimal probe; research failure returns unavailable |
| Diagnostics | Authenticated `/api/system/readiness` | Detailed storage/model/auth status stays private |
| Browser authentication | `WORKSPACE_USER=owner`, generated `WORKSPACE_PASSWORD` | Existing single-owner private workspace |
| API authentication | Generated `WORKSPACE_API_KEY` | Separate server credential; never expose in browser code |
| Automatic deployments | Off | Release exact verified commit manually |

No vendor key is needed to start the private app. Missing licensed odds/backend credentials must continue to display unavailable states. `ODDS_BACKEND_URL` and `ODDS_BACKEND_READ_TOKEN` are optional server-only gateway configuration; a separate verified backend service is needed for that gateway's live data. This blueprint does not create PostgreSQL, Redis, a feed scheduler, a daily hosted scan, or provider accounts.

## Cost and approval gate

The official pricing search result currently lists the equivalent 0.5 CPU/512 MB service at $7/month and persistent SSD storage at $0.25/GB/month: an estimated **$7.25/month base** for this blueprint. The pricing page's extracted live HTML did not expose its full dynamically rendered tariff, so this is an estimate, not a binding quote. Confirm the selected workspace plan, monthly service/disk total, taxes and usage charges on Render's final review screen before creating anything. [Render pricing](https://render.com/pricing)

The schema fetched directly on this date includes both `starter` and `0.5c-512mb` in `definitions.serverPlan`; keeping `starter` is therefore supported, rather than a confirmed invalid-plan bug. No authenticated Render Blueprint validation has occurred. [Official schema](https://render.com/schema/render.yaml.json), [Blueprint validation](https://render.com/docs/blueprint-spec)

## Concrete remaining external blockers

- No Render connector is exposed in this session; no Render CLI is installed on PATH; neither `RENDER_API_KEY` nor `RENDER_API_TOKEN` is configured. No Render account, workspace, billing total, service ID or public URL has been verified.
- Both available AppDeploy connections still resolve to the same previously connected account, rather than the owner account described in the handoff. Identity-only reads were performed; no secrets, deployments or account settings were changed. This does not block preparing Render, but it blocks claiming an AppDeploy owner cutover.
- Docker now answers locally (29.8.1). That resolves the previous daemon-access symptom; it does not itself prove a fresh image build or container acceptance. Record fresh test results separately for the final combined tree.
- Hosted authentication, disk UID/write permissions, actual memory headroom, restart persistence, public TLS and full browser workflows are unverified until a real service exists.

## Cutover procedure after account and spending approval

1. Connect the authorized Render account and existing GitHub repository. Review the exact tested commit and the final quoted cost before service creation. Do not select a free ephemeral service for persistent ledgers.
2. Apply the existing blueprint, keeping one instance and `/var/data`. Retain generated credentials in the host's secret store and retrieve the browser password through its secure dashboard. Never paste the API key into browser JavaScript, a URL, source control or evidence logs.
3. Verify unauthenticated workspace access is denied, `/healthz` is minimal, and authenticated diagnostics report the expected storage and frozen model evidence. Confirm the main workspace and `/advanced/` open through the same origin. Keep HOLD and unavailable-provider outcomes intact.
4. Use isolated synthetic records to check import replay, saved receiving receipts and outcome evaluation. Restart the service and verify those same records survive. Record release SHA, public URL, test time and observed results without credentials. No wagering, paid feed request or new scan is implied by deployment authorization.
5. Before migrating any real ledger, create and verify database-aware backups, export them securely off the service, and restore into an unused directory for a recovery check. Real user data migration is a separate reviewed step; never overwrite current production records. Only redirect users after the hosted acceptance evidence passes.

## Persistence and recovery limits

Render preserves only files beneath the attached mount. Disk services run one instance and have a short interruption during replacement; they cannot promise zero-downtime releases. Backups must execute inside the running service because its disk is unavailable to separate build/predeploy/one-off-job environments. [Render persistent disks](https://render.com/docs/disks)

Use the existing SQLite-aware `next_app/backup.py` rather than copying active database files:

```sh
python next_app/backup.py --help
```

It snapshots `workspace.sqlite3`, `research.sqlite3` and `edgeodds.sqlite3`, verifies checksums/integrity, and refuses to restore into an existing directory. Its manifest explicitly records that snapshots are individually consistent, not one transaction across all databases. A backup left on the same disk is not an independent disaster-recovery copy. Off-host backup scheduling and alerts are not configured or claimed.

Render's filesystem snapshots are not a substitute for application-consistent database backups; its documentation warns against disk-snapshot restore for custom database recovery. Keep a verified SQLite backup/restore path and separate secure export. [Render recovery guidance](https://render.com/docs/disks#restoring-a-custom-database)
