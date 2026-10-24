# Receiving60 prediction API

`POST /api/receiving60/predict` scores the installed `receiving60-logistic-v1`
artifact. `GET /api/receiving60/readiness` returns integrity and readiness details.
Both accept your `Authorization: Bearer <WORKSPACE_API_KEY>` header. Browser
clients can use workspace login plus their existing workspace token instead.
The Node research runtime must be built and running; Render's Docker image
includes it. No external odds provider is needed for this scorer.

## Request

Send JSON with exactly two fields, `request` and `history`. Unknown fields are
rejected. The target is NFL regular-season WR/RB/TE full-game receiving yards
greater than or equal to 60, conditional on a recorded player row.

`request` must contain exactly:

| Field | Value |
| --- | --- |
| `playerId`, `gameId` | Stable IDs for the target player and game |
| `kickoffAt` | Future scheduled kickoff |
| `decisionAt` | Decision time, before kickoff, not in the future |
| `league` | `NFL` |
| `position` | `WR`, `RB`, or `TE` |
| `seasonType` | `REG` |
| `period` | `FULL_GAME` |
| `stat` | `receiving_yards` |
| `threshold` | Numeric `60` |
| `comparison` | `>=` |

Each history row must contain exactly `playerId`, `gameId`, `kickoffAt`,
`resolvedAt`, `observedAt`, and integer `receivingYards`. Use UTC ISO timestamps
ending in `Z` (seconds, or exactly three decimal places). The same player must
appear in every row. Games must be unique, exclude the target game, and satisfy
`kickoffAt < resolvedAt <= observedAt < decisionAt`. Include at least three
prior games and no more than 500. Negative receiving yardage is retained.
The scorer sorts history and derives last-3/last-8 averages, hit rates and the
number of supplied prior games. Supply the complete relevant recorded history;
omitting rows changes these features and is not detected automatically.

## Synthetic request example

Set `EDGEBOARD_URL` to your HTTPS Render URL and `WORKSPACE_API_KEY` privately in
your local environment. This example creates **synthetic input**, not a real
player prediction. Replace the IDs, schedule and history with actual records
for research use. It prints the response without printing your API key.

```python
import json, os
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen

now = datetime.now(timezone.utc).replace(microsecond=0)
stamp = lambda value: value.isoformat().replace('+00:00', 'Z')
payload = {
    'request': {
        'playerId': 'synthetic-player', 'gameId': 'synthetic-future-game',
        'kickoffAt': stamp(now + timedelta(days=7)), 'decisionAt': stamp(now),
        'league': 'NFL', 'position': 'WR', 'seasonType': 'REG',
        'period': 'FULL_GAME', 'stat': 'receiving_yards',
        'threshold': 60, 'comparison': '>='
    },
    'history': [
        {'playerId': 'synthetic-player', 'gameId': f'synthetic-past-{days}',
         'kickoffAt': stamp(now - timedelta(days=days)),
         'resolvedAt': stamp(now - timedelta(days=days) + timedelta(hours=3)),
         'observedAt': stamp(now - timedelta(days=days) + timedelta(hours=4)),
         'receivingYards': yards}
        for days, yards in [(21, -5), (14, 60), (7, 80)]
    ]
}
base = os.environ['EDGEBOARD_URL'].rstrip('/')
if not base.startswith('https://'):
    raise ValueError('Use your HTTPS deployment URL')
request = Request(base + '/api/receiving60/predict',
    data=json.dumps(payload).encode(), headers={
        'Authorization': 'Bearer ' + os.environ['WORKSPACE_API_KEY'],
        'Content-Type': 'application/json'})
try:
    with urlopen(request, timeout=30) as response:
        print(response.status, response.read().decode())
except HTTPError as error:
    print(error.code, error.read().decode())
```

## Response and limits

HTTP `200` means a numeric estimate was calculated, **not** that the model is
live-approved. The response includes `probability`, `rawProbability`,
`calibratedProbability`, `features` with `featureNames`, model version, artifact
hashes, player/game IDs and decision time. It retains `status: HOLD`,
`liveApproved: false`, `productionEnabled: false`, `executionEnabled: false`
and `verifiedPositiveEv: false`.

`inputVerification` is `UNVERIFIED_CLIENT_SUPPLIED_HISTORY`. A probability is
conditional on an eventual recorded player row; it does not verify participation,
current roster eligibility or the supplied history. `uncertainty` and
`expectedValue` are null. Calibration was selected in-sample; 2025 diagnostics
are consumed. This endpoint adds access to the frozen scorer, not new validation.

HTTP `422` returns `estimateAvailable: false`, `probability: null` and a reason,
such as `INVALID_REQUEST_SCHEMA`, `UNSUPPORTED_TARGET`, `INVALID_DECISION_CLOCK`,
`MODEL_NOT_AVAILABLE_AS_OF_DECISION`, `HISTORY_NOT_AVAILABLE_AS_OF_DECISION`,
or `INSUFFICIENT_HISTORY`. Artifact integrity failure returns `503`, and an
unavailable research process also returns `503`. Malformed JSON returns `400`.
Authentication failure returns `401` on the password-protected deployment.

Inputs are not fetched or saved by this endpoint. No receipt is automatically
entered into the prediction ledger. Keep original request/response pairs with
their source provenance if you plan forward validation.

## Optional saved research receipts

The browser lab provides game-by-game history entry, optional JSON import and a
separate **Save research receipt** action. To save from an API client, send
`POST /api/receiving60/receipts` with your API key and exactly:

```json
{
  "inputMode": "supplied",
  "input": {"request": {}, "history": []},
  "expectedArtifactSha256": "canonical artifact hash from your score response"
}
```

Replace `input` with the complete valid request described above and use the
64-character `canonicalArtifactSha256` returned by the scorer. For synthetic
test inputs, set `inputMode` to `synthetic`. These input labels are client
declarations, not independently verified provenance.

The server recalculates the input before saving; it never accepts a score
receipt from a client. An artifact mismatch returns `409`. Invalid history or
clock checks return the scorer's `422` without saving. Numeric estimates are
required for storage. The record preserves the request, computed score,
server `recordedAt`, input label and `contentSha256`. New records return `201`;
an identical stored request/score/label returns the original record with `200`.
The hash covers sorted, compact JSON of the stored content excluding ID,
recorded time and the hash itself (Python JSON defaults, ASCII escaping).

`GET /api/receiving60/receipts` lists the newest 50 summaries and a `nextCursor`.
Use `GET /api/receiving60/receipts?before=<nextCursor>` for the next page.
`GET /api/receiving60/receipts/<id>` retrieves the original request and score.
All routes use the existing workspace authentication. The browser can view and
download saved records after reload.

Records live in `workspace.sqlite3` on Render's persistent disk. SQLite triggers
block updates and deletion through normal application/database operations; the
record and audit entry are saved in one transaction. This is not an externally
attested timestamp or a tamper-proof system against a database administrator.
Saved records remain `UNVERIFIED_INPUT_RESEARCH_ONLY`, with `HOLD` and no live
approval. Saving does not verify sources or create a qualified forward-validation
cohort. Workspace JSON exports do not include these full records; use their
individual download endpoints or back up the workspace SQLite database.
