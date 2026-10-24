# Deploy EdgeBoard on Fly.io

Fly.io is the selected host after Railway temporarily paused new signups.
The account signup is separate from authorizing this workspace or a CLI to use
your account. No live app, Machine or volume has been created by this change.

## Prepared configuration

The repository root includes `fly.toml`. It selects the `fly-runtime` Docker
target, a volume named `edgeboard_data` at `/var/data`, HTTPS, port 10000 and
the existing `/healthz` probe. It defaults to one shared CPU with 1 GB RAM in
`iad`. Automatic stopping is off so background research jobs continue while
the browser is idle. This is an always-on resource configuration; review billing
before launching. Fly's current pricing lists 1 GB shared CPU at $6.70 per
30 days in `iad`, plus volume, network and other applicable usage charges.

The Fly image starts its init process as root only to initialize mount-directory
ownership. Python and Node start as UID/GID 10001. Startup refuses a Fly runtime
without an actual mount at `/var/data`. Existing database file ownership is not
recursively changed. The default image for other hosts remains unprivileged.

## Launch from a trusted terminal

Use Fly's official CLI installation instructions, then clone or open this branch:

```sh
git clone --branch codex/render-private-api https://github.com/danteclaird98/SportsBettingApp.git
cd SportsBettingApp
fly auth login
fly launch --copy-config --no-deploy --ha=false --name YOUR_UNIQUE_APP_NAME --region iad
```

Replace `YOUR_UNIQUE_APP_NAME` with the name you want. If you already created an
app, set `app` in `fly.toml` to that existing app name instead of creating another.
The committed `edgeboard-replace-me` name is only a template, not a reserved app.
Check that the generated config retains `build-target = "fly-runtime"` and
the mount at `/var/data`. Do not add Postgres or Redis for this SQLite workflow.

Create a private credentials file once on your trusted device. This prints no
credential values and refuses to overwrite an existing file:

```sh
python - <<'PY'
import os, secrets
descriptor = os.open('.env.fly', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(descriptor, 'w') as target:
    target.write('WORKSPACE_PASSWORD=' + secrets.token_urlsafe(32) + '\n')
    target.write('WORKSPACE_API_KEY=' + secrets.token_urlsafe(32) + '\n')
print('Saved private credentials in .env.fly; keep a secure copy.')
PY
fly secrets import --stage < .env.fly
fly deploy --ha=false
fly status
```

`.env.fly` is ignored by Git. Use your local password/key privately; Fly stores
secret values encrypted and does not return them in ordinary secret listings.
Keep them in a password manager and out of chat. Username is `owner`.

`--ha=false` matters: the three SQLite databases use one Machine and one volume.
Independent Machines with different volumes do not share records. This setup
accepts downtime during maintenance or host failure and requires independent
backups; it is not a replicated or highly available database deployment.
Fly may prompt to create the configured volume during first deployment.

## After deployment

Open the actual `https://YOUR_APP_NAME.fly.dev` URL. Verify the public health
probe, private login and API authentication. Save a synthetic receipt, restart
the Machine, and retrieve that same record. Follow [OPERATIONS.md](OPERATIONS.md)
for an isolated backup/restore test and keep a backup outside the app's volume.

Source history remains unverified and the model remains HOLD. Deploying the
service does not provide sports data, prove calibration or enable wagering.

## Verification performed before launch

The TOML syntax and documented port/mount/image settings are checked locally.
`fly config validate --strict` requires a Fly login/token; platform validation
must be completed in your authenticated account before deploying.
The Docker smoke check is:

```sh
docker build --target fly-runtime -f next_app/Dockerfile -t edgeboard-fly:local .
python next_app/tests/container_check.py --image edgeboard-fly:local --fly
```

This verifies a local root-owned volume, missing-mount refusal, unprivileged
application processes, authentication, scoring, saved receipts, backups and
restart recovery. It does not verify your Fly account, domain or real volume.

Official references:
- https://fly.io/docs/flyctl/install/
- https://fly.io/docs/reference/configuration/
- https://fly.io/docs/flyctl/deploy/
- https://fly.io/docs/volumes/overview/
- https://fly.io/docs/about/pricing/
