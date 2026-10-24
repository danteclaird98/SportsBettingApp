# Deploy EdgeBoard on Railway

Railway is the selected hosting target. The repository's `railway.json` uses
the existing Docker image, `/healthz`, and restart-on-failure settings. No live
Railway project has been created by this change.

## Account setup

1. Sign in at https://railway.com/ with GitHub. Review the current pricing and
   usage controls before creating a paid deployment. Hobby has a $5 monthly
   minimum including $5 usage; actual usage can cost more.
2. Create a project from `danteclaird98/SportsBettingApp`. Select branch
   `codex/render-private-api` (the branch name remains for continuity). Keep the
   repository root as the service root so Docker can copy `edgeodds` and
   `next_app`. Root-level `railway.json` selects `next_app/Dockerfile`.
3. Attach one persistent volume to the service at **`/var/data`**. Start small
   and review volume charges. Keep one service replica; SQLite files are not
   shared across independently running replicas.
4. Set these service variables privately:

   | Variable | Value |
   | --- | --- |
   | `WORKSPACE_USER` | `owner` |
   | `WORKSPACE_PASSWORD` | A newly generated random password, at least 24 characters |
   | `WORKSPACE_API_KEY` | A separate random app API key, at least 32 characters |
   | `RAILWAY_RUN_UID` | `0` |

   Railway documents its volumes as root-owned. The startup script initializes
   ownership of `/var/data` only, then uses `setpriv` to run Python and Node as
   UID 10001. Existing files are not recursively reassigned. An imported volume
   must already have app-owned database files. If a restore CLI ran as root,
   assign its restored directory and individual database files to UID/GID
   10001 before switching the service to those files. The script refuses a Railway
   environment whose reported volume mount is absent or at a different path.
5. Disable automatic GitHub deployments if you want to review each release.
   This switch is an account/service setting, not controlled by `railway.json`.
   Review staged settings before deploying. Leave the custom start command
   unset so the image's init/start command is used.
6. Generate a public domain for the service's HTTP port. The app uses Railway's
   `PORT` variable; the fallback is 10000. Wait for the deployment health check
   to pass and open its HTTPS URL.

No external odds-provider credentials are required for the supplied-history
receiving60 scorer. Your app API key does not itself supply sports data.

## Verify before using saved records

- `/healthz` should return only `{"status":"ok"}`.
- The board, advanced suite and data APIs should require authentication.
- Sign in with `owner` and your workspace password. Keep keys out of chat and
  screenshots; retrieve them through Railway's private variable controls.
- Calculate and save one clearly labeled synthetic receiving60 receipt.
- Restart the service and verify the same receipt is still available.
- Create, verify and copy a SQLite-aware backup off the service; see
  [OPERATIONS.md](OPERATIONS.md). Host volume snapshots are additional recovery
  support, not a substitute for a tested independent backup.

`python next_app/tests/container_check.py --railway` exercises a local
root-owned volume, privilege dropping, scoring, receipts, backup/restore and
restart recovery. This does not establish that your Railway account or its
specific volume/domain settings are correct; verify the deployed URL too.

References checked for this configuration:
- https://docs.railway.com/builds/dockerfiles
- https://docs.railway.com/config-as-code/reference
- https://docs.railway.com/volumes
- https://railway.com/pricing
