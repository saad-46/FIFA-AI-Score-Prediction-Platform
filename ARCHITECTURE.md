# Architecture

System overview for the FIFA AI Score Prediction Platform, current as of the
2026-07-02 production audit. See `CHANGELOG.md` for what changed in that audit.

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 (App Router, TypeScript), Tailwind CSS — `frontend/` |
| Backend API | FastAPI, Python 3.12, Pydantic v2, Uvicorn — `backend/app/` |
| Database | PostgreSQL via Supabase, accessed with SQLAlchemy 2.0 async (asyncpg) |
| Auth | Supabase Auth (JWT), verified server-side via `SUPABASE_JWT_SECRET` |
| ML | XGBoost (regressors + classifier), scikit-learn, SHAP, Optuna, pandas/numpy/scipy |
| Tournament engine | Custom Monte Carlo simulator using `ProcessPoolExecutor` |
| Cache | In-process TTL cache (stdlib only, no Redis) — `backend/app/core/cache.py` |
| Frontend deploy | Vercel |
| Backend deploy | Render (2 uvicorn workers) |

The frontend (`frontend/`) is a Next.js 15 app that consumes the FastAPI
backend over HTTP and talks to Supabase directly for auth. It is **out of
scope** for this audit — none of the six agents touched it — and is mentioned
here only for completeness.

## Component diagram

```
                          ┌─────────────────────┐
                          │   Next.js Frontend   │  (frontend/, Vercel)
                          │  App Router + Tailwind│
                          └──────────┬───────────┘
                                     │ HTTPS (JSON)
                                     ▼
                     ┌───────────────────────────────┐
                     │        FastAPI backend          │  (backend/app/, Render)
                     │  app/main.py — lifespan, CORS,  │
                     │  GZip, exception handlers        │
                     └───────────────┬─────────────────┘
                                     │
        ┌────────────────────────────┼─────────────────────────────┐
        ▼                            ▼                              ▼
┌───────────────┐          ┌──────────────────┐          ┌──────────────────────┐
│  API routers   │          │   ML layer         │          │  Tournament engine     │
│  app/api/v1/   │          │  app/ml/           │          │  app/ml/               │
│  endpoints/    │          │  - predictor.py     │          │  tournament_simulator.py│
│  predictions,  │◄────────►│  - feature_engineer │◄────────►│  - Monte Carlo (48      │
│  teams,        │          │    ing.py            │          │    teams, ProcessPool  │
│  matches,      │          │  - poisson.py        │          │    Executor)           │
│  analytics,    │          │  - calibration.py    │          │  - FIFA 2026 reference │
│  tournament     │          │  - explainability.py │          │    data (app/data/     │
└───────┬────────┘          │    (SHAP)             │          │    fifa_2026/)         │
        │                    └─────────┬────────────┘          └───────────┬───────────┘
        │                              │                                    │
        ▼                              ▼                                    │
┌────────────────────┐      ┌─────────────────────┐                        │
│  Services layer     │      │  Model bundle (disk)  │                        │
│  app/services/*.py   │      │  xgboost_model.pkl,   │◄───────────────────────┘
│  (business logic,    │      │  scaler.pkl,          │   (shares predictor +
│   query building)     │      │  feature_importance   │    matchup cache)
└─────────┬───────────┘      │  .json                │
          │                    └───────────────────────┘
          ▼
┌─────────────────────┐
│  SQLAlchemy 2.0 async │
│  app/db/database.py   │
│  pool_size=5,          │
│  max_overflow=5        │
└─────────┬────────────┘
          ▼
┌─────────────────────┐
│  PostgreSQL (Supabase)│
│  teams, matches,       │
│  saved_predictions,    │
│  profiles              │
└───────────────────────┘
```

## Request lifecycle — `POST /api/v1/predictions/predict`

1. `predictions.py` receives `PredictionRequest` (home_team, away_team,
   tournament, neutral_venue), validated by Pydantic v2 (teams must differ,
   whitespace stripped).
2. `prediction_service.run_prediction()` calls `get_predictor()` — a process
   singleton `MatchPredictor` loaded once at startup from the pickled model
   bundle (`app/ml/models/predictor.py`).
3. The predictor pulls the cached historical match DataFrame
   (`load_matches_dataframe()`, 6h TTL, `app/ml/data/loader.py`) and builds a
   team → row-index map (`build_team_index`, vectorized via `groupby`).
4. `build_feature_vector()` (`app/ml/features/feature_engineering.py`)
   computes rolling form (5/10/20-match windows), head-to-head record, rest
   days, Elo, and derived differential/interaction features for the pair.
5. Features are scaled (`StandardScaler`, fit during training) and fed to two
   `XGBRegressor`s (home/away expected goals) and one `XGBClassifier`
   (home win / draw / away win).
6. A `PoissonEngine` turns (home_xg, away_xg) into a full scoreline
   probability matrix; its outcome probabilities are blended 60/40 with the
   calibrated classifier probabilities (`_blend_probabilities`).
7. If SHAP is available, `PredictionExplainer` attributes the predicted
   outcome to the top positive/negative features.
8. The service enriches the result with head-to-head stats and rule-based
   insights (e.g. home-advantage), respecting `neutral_venue`.
9. Result is cached in-process (keyed by `prediction_id`) so a follow-up
   `POST /predictions/{id}/save` can persist it without recomputation, and
   returned as `PredictionResult`.

## Request lifecycle — `POST /api/v1/tournament/simulate`

1. `tournament.py` validates `TournamentSimulationRequest` — either 12 groups
   of 4 client-submitted teams (48 total, no duplicates, enforced by a
   Pydantic v2 `model_validator`) or `use_fifa_2026_groups: true`, which
   substitutes the official reference data from
   `app/data/fifa_2026/groups.json` instead.
2. A shared `MatchPredictor` + historical DataFrame are lazily initialized
   once per process (module-level cache in `tournament.py`).
3. `TournamentSimulator._precompute_matchups()` builds every pairwise matchup
   (1128 pairs for 48 teams) in one batched call to
   `MatchPredictor.predict_batch()` — one vectorized model inference instead
   of 1128 sequential ones — and caches expected goals / win probabilities
   per pair.
4. `simulate_tournament()` runs the actual Monte Carlo loop
   (`asyncio.to_thread` off the event loop, since it's CPU-bound): the
   requested `n_simulations` are split across `cpu_count() - 1` worker
   processes via `ProcessPoolExecutor`, each running `_run_simulation_batch`
   — full group stage, tiebreak-ranked qualification, R32 bracket generation,
   and single-elimination knockout with extra-time/penalty handling.
5. Per-batch failures are tracked; if more than 25% of requested simulations
   are lost, `TournamentSimulationError` is raised (mapped to HTTP 503)
   instead of silently returning skewed probabilities. Otherwise results are
   normalized against however many simulations actually completed.
6. Aggregated per-team stage-reach probabilities are returned as
   `TournamentSimulationResponse`.

## Key design decisions

- **In-process TTL cache instead of Redis** (`app/core/cache.py`). This
  stack has no Redis dependency anywhere; a small stdlib-only
  `async_ttl_cache` decorator is applied to endpoints like `/analytics/global`
  and `/teams/top` that are read-heavy but only need coarse freshness (the
  underlying match DataFrame itself already refreshes on a 6h TTL). Simple
  FIFO eviction past `max_size`, not a general LRU — deliberately scoped to
  low-cardinality endpoint argument combinations, not a general-purpose cache.
- **`ProcessPoolExecutor` for Monte Carlo, not threads.** Tournament
  simulation is pure-Python CPU-bound work (no I/O to overlap), so threads
  would be blocked by the GIL; separate processes give real parallelism.
  Pickling overhead for the matchup cache was measured at ~1.5ms/submit
  (Performance Engineer's audit) — negligible relative to per-batch compute.
- **Poisson + classifier blend, not either alone.** The Poisson engine
  captures the natural shape of a low-scoring-sport score distribution; the
  XGBoost classifier captures non-linear patterns (Elo gaps, home advantage)
  the Poisson model can't see on its own. Fixed 60/40 blend weights
  (`_POISSON_WEIGHT` / `_CLASSIFIER_WEIGHT` in `predictor.py`).
- **6-hour TTL on the historical match DataFrame**, not per-request DB
  reads. Feature engineering needs the *entire* match history in memory to
  compute rolling stats; re-querying and rebuilding that on every request
  would dominate latency. A background/lazy refresh keeps predictions
  reasonably fresh without paying that cost per call.
- **Fail loudly on startup if the DB is unreachable** (`app/main.py`
  lifespan). The ML model is allowed to be missing (falls back to historical
  averages), but the database is a hard dependency for nearly every route, so
  a misconfigured `DATABASE_URL` now raises at startup instead of the app
  reporting healthy while every DB-backed route 500s later.
- **Synthetic-data honesty over fake precision.** Where the schema doesn't
  support a feature (goal-distribution-by-minute has no per-goal timestamp
  data), the response schema says so explicitly (`is_synthetic: bool = True`
  on `GoalDistributionPoint`) rather than fabricating realistic-looking
  numbers. See `KNOWN_ASSUMPTIONS.md`.
- **FIFA 2026 reference data as static, versioned JSON**, not a live feed.
  `app/data/fifa_2026/{groups,schedule,venues}.json` are extracted once from
  an official source PDF and loaded via `functools.lru_cache`-wrapped
  accessors (`app/data/fifa_2026/__init__.py`) — no external API dependency,
  no risk of silently drifting from the source-of-truth extraction.

## Directory map

```
backend/app/
├── main.py                 # FastAPI app, lifespan, middleware, exception handlers
├── core/                   # config.py (Settings), security.py (JWT), cache.py
├── api/v1/
│   ├── router.py            # mounts all endpoint routers
│   └── endpoints/           # predictions, teams, matches, analytics, tournament
├── services/                # business logic between endpoints and DB/ML
├── models/                  # SQLAlchemy ORM models (Team, Match, SavedPrediction)
├── schemas/                  # Pydantic v2 request/response schemas
├── db/database.py            # async engine, session factory, pool config
├── data/fifa_2026/           # static reference data + loader (see README.md there)
└── ml/
    ├── train.py               # offline training pipeline
    ├── hyperparameter_search.py # Optuna search
    ├── calibration.py          # isotonic/Platt calibration
    ├── explainability.py       # SHAP-based PredictionExplainer
    ├── poisson.py               # PoissonEngine
    ├── tournament_simulator.py  # Monte Carlo engine
    ├── features/feature_engineering.py
    ├── data/loader.py           # cached DataFrame loader
    └── models/predictor.py      # MatchPredictor (inference)

database/                    # schema.sql, seed.sql, seed_fifa_2026_teams.sql
frontend/                    # Next.js 15 app (out of audit scope)
```
