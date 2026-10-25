# API Documentation

Base URL: `{host}` + `API_V1_PREFIX` (default `/api/v1`) for all routers
below; `/health` and `/` are mounted directly on the app, no prefix.

Source of truth for this document: `backend/app/api/v1/router.py` and the
endpoint modules under `backend/app/api/v1/endpoints/`, read directly as of
2026-07-02. Interactive OpenAPI docs are available at `/docs` (and `/redoc`)
when `DEBUG=true`; they are disabled in production (`app/main.py`).

Auth: Bearer JWT (Supabase-issued, HS256, verified against
`SUPABASE_JWT_SECRET`). Endpoints marked **auth required** use
`get_current_user` (401 if missing/invalid/expired token). Endpoints marked
**auth optional** use `get_optional_user` (behaves as anonymous on missing or
invalid token, never errors).

---

## Health

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/` | none | Root info: app name, version, docs link |
| GET | `/health` | none | `{status, version, model_loaded, environment}` — used for deploy health checks |

---

## Predictions — `/api/v1/predictions` (`predictions.py`)

| Method | Path | Auth | Status codes | Description |
|---|---|---|---|---|
| POST | `/predictions/predict` | optional | 200, 422, 500 | Run a match prediction. Body: `PredictionRequest` (`home_team`, `away_team`, `tournament?`, `neutral_venue`). Returns `PredictionResult`. |
| POST | `/predictions/{prediction_id}/save` | **required** | 201, 401, 404, 500 | Persist a previously-run prediction (must still be in the in-process cache — re-run if expired). Returns `SavedPredictionResponse`. |
| GET | `/predictions/saved` | **required** | 200 | Paginated (`page`, `page_size` ≤ 100) list of the caller's saved predictions. |
| DELETE | `/predictions/saved/{prediction_id}` | **required** | 204, 404 | Delete one of the caller's saved predictions. |
| GET | `/predictions/accuracy` | **required** | 200 | `AccuracyStats` — total/correct/accuracy ratio over the caller's saved predictions that have been graded (`was_correct` not null). |

`PredictionResult` includes: predicted score, expected goals, win/draw/loss
probabilities, most-likely scoreline + top scorelines, an optional SHAP-based
`prediction_explanation`, `confidence_score`, `model_version`, rule-based
`insights`, and `head_to_head` stats.

---

## Teams — `/api/v1/teams` (`teams.py`)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/teams/search?q=` | none | Search teams by name (`q` min length 2). Returns `list[TeamResponse]`. |
| GET | `/teams/top?limit=&tournament=` | none | Top teams by win rate (`limit` 1-50, default 10). Cached in-process 60s via `async_ttl_cache`. Returns `list[TeamStatsResponse]`. |
| GET | `/teams/head-to-head?home_team_id=&away_team_id=` | none | Head-to-head record between two teams by ID. Returns `HeadToHeadResponse`. |
| GET | `/teams/{team_id}` | none | Single team by ID. 404 if not found. Returns `TeamResponse`. |
| GET | `/teams/{team_id}/stats?tournament=&years=` | none | Full stats for one team (wins/draws/losses, goals, form). 404 if team not found. |
| GET | `/teams/{team_id}/trend?months=` | none | Performance trend over time (`months` 1-120, default 24). Returns `list[PerformanceTrendPoint]`. |

Route ordering note: `/search` and `/top` and `/head-to-head` are declared
before `/{team_id}` in the router so they aren't shadowed by the path
parameter.

---

## Matches — `/api/v1/matches` (`matches.py`)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/matches` | none | Paginated match history. Query: `page`, `page_size` (≤100), `team`, `tournament`, `year`, `from_date`, `to_date`. Returns `PaginatedMatchResponse`. **Not WC-only scoped** — see note below. |
| GET | `/matches/tournaments` | none | All distinct tournament names. Returns `list[str]`. |
| GET | `/matches/tournaments/{tournament}/stats` | none | Stats for one tournament. Returns `TournamentStatsResponse`. |
| GET | `/matches/analytics/scorelines?tournament=` | none | Most common final scorelines with frequency/percentage. Returns `list[ScorelineFrequency]`. |
| GET | `/matches/{match_id}` | none | Match detail by id, including per-team box-score stats (possession/shots/corners/etc.) from `team_statistics` when available. Returns `MatchDetailResponse`. 404 if not found. Registered last among GET routes so it doesn't shadow `/tournaments`, `/tournaments/{tournament}/stats`, and `/analytics/*`. |

---

## Analytics — `/api/v1/analytics` (`analytics.py`)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/analytics/dashboard` | optional | `DashboardStatsResponse`: total matches/teams, and — only if authenticated — the caller's prediction count/accuracy, 5 most recent saved predictions, top 5 teams by win rate, and next 5 upcoming fixtures. `total_matches_analyzed` is **not WC-only scoped** — see note below. |
| GET | `/analytics/global` | none | `GlobalAnalyticsResponse`: total matches/goals, avg goals/match, home/draw/away rates, goals-by-year, top 10 tournaments by match count. Computed via full-history pandas aggregation, cached in-process 60s (`_compute_global_analytics`, `async_ttl_cache`). |
| GET | `/analytics/model-metrics` | none | `ModelMetricsResponse`: accuracy/MAE/RMSE, last trained timestamp, training sample count, model version. Reads `metrics.json` / `training_report.json` from the model directory (produced by `train.py`); zeros/`"unknown"` if training hasn't been run yet. |
| GET | `/analytics/feature-importance` | none | `FeatureImportanceResponse`: sorted `[{feature, importance}]` averaged across all three models, plus `model_version` and `total_features`. Reads `feature_importance.json` (`FEATURE_IMPORTANCE_PATH` setting). **404** with an actionable message if the file doesn't exist (training hasn't been run). Not listed in the root `README.md`'s endpoint table — confirmed present in the current code. |

---

## Tournament — `/api/v1/tournament` (`tournament.py`)

| Method | Path | Auth | Status codes | Description |
|---|---|---|---|---|
| GET | `/tournament/2026/groups` | none | 200 | The official FIFA World Cup 2026 groups (A-L, 48 teams). Returns `Fifa2026GroupsResponse`. Read-only, sourced from `app/data/fifa_2026/groups.json`. |
| GET | `/tournament/2026/schedule?stage=&venue_city=` | none | 200 | The official 104-fixture schedule, optionally filtered by `stage` (`group_stage`, `round_of_32`, `round_of_16`, `quarter_final`, `semi_final`, `third_place`, `final`) and/or `venue_city`. Returns `Fifa2026ScheduleResponse`. |
| POST | `/tournament/simulate` | none | 200, 422, 503, 500 | Run Monte Carlo simulation. Body: `TournamentSimulationRequest` — either `groups` (12 groups × 4 teams, validated to be exactly 48 unique names) or `use_fifa_2026_groups: true` to simulate the real bracket without submitting team names; `n_simulations` (100-100000, default 10000). Returns `TournamentSimulationResponse` — per-team probability of reaching each stage (`group`, `r32`, `r16`, `qf`, `sf`, `third_place`, `final`, `winner`). **503** if the predictor model isn't loaded, or if more than 25% of simulation batches failed (`TournamentSimulationError`). |

`TournamentSimulationRequest` validation (Pydantic v2 `model_validator`):
when `use_fifa_2026_groups` is false, `groups` must be present, sum to
exactly 48 teams, and contain no duplicate team names across groups —
otherwise a 422 is returned.

**Open item, flagged 2026-07-04 (see `KNOWN_ASSUMPTIONS.md`):** `GET
/api/v1/matches` and `/analytics/dashboard`'s `total_matches_analyzed` query/
count the full `matches` table (~49,389 rows, 1872-2026, all competitions),
not just the 419-row WC-only corpus the ML pipeline is now scoped to
(`app/ml/data/loader.py`'s `data_source IS NOT NULL` filter). This was only
noticed once the live database became reachable and queryable. It is an open
product decision, not a bug — see `KNOWN_ASSUMPTIONS.md` for detail.

---

## Error format

Validation errors (422) are returned as:
```json
{"status": "error", "message": "Validation error", "details": [{"loc": [...], "msg": "...", "type": "..."}]}
```
Unhandled exceptions are caught globally and returned as a generic 500
without leaking internal exception text:
```json
{"status": "error", "message": "Internal server error"}
```
(see `general_exception_handler` in `app/main.py`).

---

## Not yet covered by this document

The root `README.md`'s endpoint list predates this audit and is missing
`/analytics/feature-importance` and the entire `/tournament/*` router (all
three routes). This document reflects the endpoint files as they exist on
disk today; treat this file, not the root README, as authoritative for the
API surface.
