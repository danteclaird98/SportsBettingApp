# Operating the private workspace

## Readiness and recovery

Fly.io uses `GET /healthz`. This is the only intentional unauthenticated
application route; it returns only `{"status":"ok"}` with 200, or
`{"status":"unavailable"}` with 503. It checks workspace storage readability and
the installed model's integrity through the Node research process. It does not
check external sports-data availability, disk free space or prediction validity.

Authenticated clients can use `GET /api/system/readiness` for component booleans
and whether browser/API credentials are configured. No credential values appear.
The cloud launcher requires the built research process, waits for readiness,
and exits if that process dies. SIGTERM stops the Python service and its child.

## Create and verify a backup

The image includes a standard-library backup CLI. Use a new destination name:

```sh
python next_app/backup.py create --data-dir /var/data --destination /var/data/backups/2026-10-24-first
python next_app/backup.py verify /var/data/backups/2026-10-24-first
```

Choose a fresh dated destination for each run. Creation refuses an existing
directory. The tool uses SQLite's backup API, so committed WAL data is included
without copying live database files directly. A manifest contains the database
names, sizes, SHA-256 checksums, creation time and any missing optional databases.
`workspace.sqlite3` is required; default `research.sqlite3` and `edgeodds.sqlite3`
are included when present. A separately configured `--odds-db` outside the data
directory needs its own SQLite-aware backup.

Snapshots are individually consistent per database. They do not guarantee one
simultaneous transaction across all three databases. Keep sensitive backup files
private. Copy completed snapshots off the service's disk through your account's
supported file transfer/storage controls, and establish retention appropriate to
your available disk space. No off-host upload, retention schedule or automatic
deletion is configured by this change.

## Test restore without overwriting the running app

```sh
python next_app/backup.py restore /path/to/copied-backup --destination /path/to/new-restored-data
python next_app/server.py --data-dir /path/to/new-restored-data --port 8080 --require-research
```

Perform the restore test on an isolated machine or after stopping the original
service; the research backend uses loopback port 8091. The restore destination
must not exist. Verification checks hashes and SQLite integrity before copying,
then rechecks the restored files. Failed backup/restore attempts can leave a
partial new directory for inspection; they never overwrite an existing directory.

Verify expected saved receipts, wager counts and audits before selecting restored
data for production. The server must be stopped before switching data directories.
Do not restore by copying a database over an active process's open file.

## Small release checklist

1. Confirm CI and the Docker build pass for the commit being deployed.
2. Create and verify a backup; keep an independent copy.
3. Deploy manually with `fly deploy --ha=false` after reviewing the current app configuration.
4. Confirm `/healthz`, browser login and an authenticated API request.
5. Check one existing saved receipt and one synthetic calculation.
6. Confirm saved data survives a service restart.

Use the account's secret controls to rotate `WORKSPACE_API_KEY` or
`WORKSPACE_PASSWORD`, then restart/deploy. Never copy secret values into a
workspace report, URL, screenshot or GitHub issue.
