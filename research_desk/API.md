# Local API

All `/api` requests require `Authorization: Bearer <user token>`. POST uses JSON object bodies and `Content-Type: application/json`. Invalid Host/Origin is rejected. Nonfinite numbers, duplicate JSON keys and bodies above 1 MB are rejected. Requests are scoped to the token's user. UI assets are public on loopback only.

| Method | Endpoint | Behavior |
|---|---|---|
| GET | `/api/research` | Evidence-only board with computed exclusions; EV/model probability null |
| GET | `/api/wagers` | User's wager records and current settlements |
| GET | `/api/performance` | Separate mode/currency reports and exposures |
| GET | `/api/states` | User's live-state history |
| GET | `/api/limits` | User's currency limits |
| GET/POST | `/api/settings` | Per-user documented freshness settings |
| GET | `/api/coverage` | Designed, catalog, recently seen and observed dimensions; verification flags |
| GET | `/api/providers` | Credential-safe provider health and user catalog |
| GET | `/api/health` | Provider health, empty model registry, disabled execution |
| GET | `/api/audit` | Persistent user-scoped before/after audit history |
| POST | `/api/quotes` | One immutable quote; use the UI's template |
| POST | `/api/quote_batch` | `{ "quotes": [...] }`; max 10,000; whole-batch rollback on failure |
| POST | `/api/states` | Monotonic per-event state; duplicate same record ignored |
| POST | `/api/wagers` | User-reported proposed/paper/actual tracking record |
| POST | `/api/settle` | Explicit gross payout/fees, revision and source; never submits a wager |
| POST | `/api/limits` | Currency, max_open/max_group/max_daily, optional IANA timezone |
| POST | `/api/provider` | Provider discovery/retrieval/import actions below |
| POST | `/api/evaluate` | `{ "rows": [...], "train_end": ISO, "validation_end": ISO }` descriptive audit |

Provider body requires `provider="the_odds_api"` and action:

- `sports`: authorized catalog retrieval.
- `events`: exact `sport` key.
- `markets`: `sport`, exact `event_id`, optional `regions`.
- `odds`: `sport`, array `markets`, optional `regions` and `event_id`. Without event ID only h2h/spreads/totals/outrights are accepted. Extra markets use exact event ID. Returned sport/event identity is checked.
- `scan_all`: optional `max_requests` (1–20, default 5) and `regions`. Resume a persisted breadth-first cycle. Credits are not capped by the request budget.
- `import_snapshot`: decimal-format provider `payload` and actual saved `retrieved_at`; always unverified. No key required for saved-file import.

Current supported region codes: us, us2, uk, au, eu, fr, se. Multiple comma-separated regions accepted. Providers are registered in `ProviderService.adapters`; a new adapter should preserve explicit schema validation, safe health/diagnostics, identity mapping and verification boundaries. No stub provider is registered as working.

Historical rows require text id/event_id/sport/market, season, prediction_at, inputs_available_at, odds_observed_at, result_available_at, binary integer outcome, settlement_type="binary", probability, baseline_probability and decimal_odds. Executable selected records additionally require execution_at, execution_decimal_odds, execution_odds_observed_at, price_available_until, stake and fees. Optional max_execution_quote_age_seconds defaults to 300. Selection/execution flags must be booleans. Optional model_fitted_at/preprocessing_fitted_at/calibration_fitted_at and model_selected_at are checked when supplied. The utility cannot verify omitted rows or the provenance of assertions.

Unsupported actions, including `/api/execute`, are rejected. No API accepts an arbitrary provider URL, browser credential or bookmaker submission.

## Pre-launch repair additions

`GET /odds/latest` and `GET /odds/history` both require the same bearer token and loopback Host/Origin. Query parameters: `limit` (1–500, default 100), `offset` (0–1,000,000), optional `event_id`, `sportsbook`, `after` and `before` (timezone-qualified ISO source-observation bounds). Unknown/duplicate query parameters are rejected. SQL values are bound parameters. Response: `{ "items": [...], "next_offset": 100 | null }`. Latest uses source observation rather than arrival order, retains equal-time conflicts, and computes best comparable prices with the other books even when those books are outside the returned page. Unknown observation time uses retrieval for ordering only, never freshness eligibility. History returns raw immutable stored records. Offset pagination is not a frozen export; concurrent ingestion can change which rows are current between pages.

`/api/research` uses the latest view and keeps its array response. Wagers, states, limits, audit, event maps, aliases and exhausted provider failures return bounded arrays. Continue using the `X-Next-Offset` response header; absent means no next page. The UI supplies a Load more button. `/api/performance` remains an aggregate over the full user ledger rather than a page of wagers.

`POST /api/event_maps`: provider, provider_event_id, canonical event_id, sport, league, start_at, status (`active`, `postponed`, `cancelled`), revision (positive integer), reason. Existing bindings require increasing revisions; changes preserve previous quotes/audit. Source IDs are scoped by provider and league. Apply explicit cross-provider mappings before importing those source IDs. A revised start time invalidates previously stored prices until a matching new quote arrives.

`POST /api/aliases`: kind (`team` or `book`), league, source, target. Records are immutable; a conflicting mapping is rejected. This administrative mapping affects future imports and does not rewrite past evidence.

`GET /api/event_maps`, `/api/aliases`, `/api/provider_failures` expose user-scoped records. Failed tasks exhaust after three attempts and remain inspectable; they can be retried in a new scan cycle after resolving the error. Storage errors return a redacted 503 suitable for retrying the same idempotent request.
