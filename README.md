# FIFA AI Score Prediction Platform

An AI-powered platform for predicting FIFA match outcomes and simulating the
FIFA World Cup 2026 tournament. A FastAPI backend serves XGBoost-based match
predictions (expected goals, win/draw/loss probabilities, SHAP explanations)
trained on a dedicated World Cup-only corpus, plus a Monte Carlo tournament
simulator built on the official 48-team, 12-group FIFA World Cup 2026 format
that is aware of real, in-progress 2026 results. A Next.js frontend is
planned to consume the API for match prediction, team analytics, and
tournament visualization — see "Current project status" below for exactly
what is and isn't done yet.

The 2026 tournament is genuinely in progress as this is written, and the
simulator and training data reflect that: real completed 2026 matches are
used as ground truth rather than re-simulated, and the model is trained on
real match data through the current point in the tournament.

## Current project status — `backend-v1.0.0`

**The backend is complete and frozen as `backend-v1.0.0`; the frontend is a
separate, not-yet-integrated track.** This session validated the backend
end-to-end against live production infrastructure (not mocks, not a local
sandbox):

- **80/80 backend tests passing** (`cd backend && pytest -q`).
- **Every headline API endpoint exercised live** against the real Supabase
  Postgres project (`<project-ref>`), including `/health`, the
  Swagger docs at `/docs`, `POST /predictions/predict`, and
  `POST /tournament/simulate`.
- **6 prediction matchups verified** end-to-end (expected goals, win/draw/loss
  probabilities, SHAP explanations all returned correctly).
- **Tournament simulations run at up to 5,000 iterations** (100 / 1,000 /
  5,000 all completed successfully) against the live 48-team, 12-group
  bracket.
- Two real bugs that could only surface against a live, reachable database
  were found and fixed this session (missing WC-only filter in the ML data
  loader; a SQLAlchemy `uuid`/`String` column-type mismatch) — see "Live
  database validation" below and `CHANGELOG.md`.

On the strength of this validation, the backend is being frozen at
`backend-v1.0.0` as **complete and ready for frontend integration**. The
`frontend/` directory in this repo already contains Next.js scaffolding
(pages, components, auth flow) from earlier exploratory work, but it has
**not** been part of this validation pass and is **not** included in the
`backend-v1.0.0` freeze — treat it as a separate, in-progress track to be
picked up and finished after this release. One open item carried into the
next phase, not resolved by this freeze: `GET /api/v1/matches` and
`/analytics/dashboard` are not yet scoped to the WC-only dataset the same way
the ML pipeline is — see "Live database validation" and
`KNOWN_ASSUMPTIONS.md` item (h) for the current, unresolved state of that
question.

## Features

- **AI match prediction** — home/away expected goals from two XGBoost
  regressors (`count:poisson` objective), plus a 3-class XGBoost classifier
  for win/draw/loss.
- **Win / draw / loss probabilities** — blended 60/40 from a Poisson
  score-matrix simulation and the calibrated classifier output.
- **Poisson score simulation** — full scoreline probability matrix and
  most-likely scorelines derived from predicted expected goals.
- **FIFA World Cup 2026 tournament simulator** — Monte Carlo simulation of
  the real 48-team, 12-group bracket (group stage → Round of 32 → Round of
  16 → quarter-finals → semi-finals → third-place → final), with real,
  already-played 2026 results substituted in instead of blindly
  re-simulating matches that have already happened.
- **SHAP explainability** — every prediction can return the top positive and
  negative feature attributions behind it.
- **Elo ratings + FIFA rankings** — a dynamic, tournament-weighted Elo system
  computed over full match history, complemented (not replaced) by official
  FIFA pre-tournament rankings as separate model features. Fixed this session
  so Elo is genuinely used at inference time, not just during training — see
  `KNOWN_ASSUMPTIONS.md` item (d) and `ELO_SYSTEM.md` for the before/after.
- **FastAPI backend** — async SQLAlchemy 2.0, Pydantic v2, in-process TTL
  caching (no Redis dependency).
- **Supabase / PostgreSQL** database, with Row Level Security — confirmed
  live and reachable this session (see "Live database validation" below).
- **Next.js frontend (planned)** — TypeScript, App Router, Tailwind CSS.
  Scaffolding already exists under `frontend/`, but it is a separate,
  not-yet-integrated track: it hasn't been part of any backend validation
  pass and is out of scope for the `backend-v1.0.0` freeze.

## Screenshots

<!-- Add screenshots here — not yet captured for this release. -->

## Tech Stack

**Backend:** Python 3.12, FastAPI 0.115, Pydantic v2, SQLAlchemy 2.0 (async,
asyncpg), Uvicorn

**Database:** PostgreSQL via Supabase

**ML:** XGBoost 2.1, scikit-learn, pandas, NumPy, SciPy, SHAP, Optuna
(hyperparameter search)

**Frontend (planned, not yet integrated):** Next.js 16 (App Router), React 19,
TypeScript, Tailwind CSS 4, Radix UI, react-hook-form + zod, SWR, Recharts,
Supabase JS client

See `backend/requirements.txt` and `frontend/package.json` for exact pinned
versions.

## Architecture

Frontend (Next.js, Vercel — planned) → FastAPI backend (Render) → services
layer → SQLAlchemy async → PostgreSQL (Supabase), with a separate ML layer
(predictor, feature engineering, Poisson engine, SHAP explainer) and a
Monte Carlo tournament engine (`ProcessPoolExecutor`-based) sitting behind
the API routers. See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full
component diagram, request lifecycles, and key design decisions — this
section deliberately doesn't repeat it. As of `backend-v1.0.0`, only the
backend half of this diagram has been built and validated end-to-end; the
frontend box is the planned next phase.

## Installation

### Prerequisites

- Python 3.12+
- Node.js 18+
- A Supabase project (PostgreSQL + Auth)

### Backend setup

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Copy and fill in your own credentials — never commit this file
cp .env.example .env
```

Provision the database (run in the Supabase SQL editor):

- **Fresh database:** `database/schema.sql` → `database/seed_wc2026.sql`
  (this is a superset of `database/seed_fifa_2026_teams.sql` and seeds 72
  teams, 419 matches, and 132 `team_statistics` rows from the processed
  WC2026 corpus).
- **Upgrading an existing database:** `database/migrations/002_wc2026_upgrade.sql`
  → `database/seed_wc2026.sql`.
- `database/seed.sql` (the older, broader 1872-2017 dataset) is left in
  place but marked superseded for the WC2026-only focus — it is optional and
  not required for the app to function.

> **Update 2026-07-04:** the WC2026 schema migration and seed above have now
> been applied to the live Supabase project (`<project-ref>`) and
> verified — see the "Live database validation" section below for exactly
> what was checked. If you're standing up a **new** instance, run the
> migration/seed yourself as described above and confirm your own row counts
> match what's documented in `DATABASE_SCHEMA.md`.

### Frontend setup

> The frontend is planned/in-progress and not part of the validated
> `backend-v1.0.0` release — see "Current project status" above. These
> commands will install and run the existing scaffolding, but it has not
> been tested against the validated backend this session.

```bash
cd frontend
npm install
cp .env.local.example .env.local
```

### Running the application

```bash
# Backend (from backend/)
uvicorn app.main:app --reload --port 8000
# API docs at http://localhost:8000/docs (when DEBUG=true)

# Frontend (from frontend/)
npm run dev
# App at http://localhost:3000
```

### Running tests

```bash
cd backend
pytest -q
```

As of this writing, this runs **80 passing tests** (up from 13 at the
project's initial commit). Run the command yourself to confirm the current
count if you've made changes.

## Environment Variables

Both `backend/.env.example` and `frontend/.env.local.example` already exist
in this repo — copy them as shown above and fill in your own values. Never
commit the resulting `.env`/`.env.local` files.

- **`backend/.env.example`** — app metadata, Supabase URL/service-role/anon
  keys, the Supabase JWT secret (for verifying frontend-issued auth tokens),
  the direct Postgres `DATABASE_URL`, allowed CORS origins, and the ML model
  file paths/version string.
- **`frontend/.env.local.example`** — the public Supabase URL/anon key, the
  backend API base URL the frontend should call, and the app's own public
  URL.

## Project Structure

```
fifa-score-predictor/
├── README.md, LICENSE
├── ARCHITECTURE.md, API_DOCUMENTATION.md, MODEL_PIPELINE.md,
│   MODEL_EVALUATION.md, TOURNAMENT_ENGINE.md, DATABASE_SCHEMA.md,
│   DATA_PIPELINE.md, FEATURE_ENGINEERING.md, ELO_SYSTEM.md,
│   RANKINGS_INTEGRATION.md, KNOWN_ASSUMPTIONS.md, TRAINING_GUIDE.md,
│   CHANGELOG.md            # docs live at repo root as individual files
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app, lifespan, middleware
│   │   ├── api/v1/endpoints/     # predictions, teams, matches, analytics, tournament
│   │   ├── core/                 # config, security (JWT), in-process cache
│   │   ├── data/
│   │   │   ├── fifa_2026/        # official 2026 groups/schedule/venues (static JSON)
│   │   │   └── processed/        # matches_historical.csv, teams_reference.csv,
│   │   │                         # match_team_stats.csv, DATA_QUALITY_REPORT.md
│   │   ├── db/                   # SQLAlchemy async engine/session
│   │   ├── ml/                   # training, feature engineering, calibration,
│   │   │   ├── models/           #   xgboost_model.pkl, scaler.pkl, predictor.py,
│   │   │   │                     #   feature_importance.json, metrics.json, etc.
│   │   │   ├── features/         #   feature_engineering.py
│   │   │   ├── data/             #   loader.py (cached inference DataFrame)
│   │   │   └── tournament_simulator.py
│   │   ├── models/               # SQLAlchemy ORM models
│   │   ├── schemas/               # Pydantic v2 request/response schemas
│   │   └── services/              # business logic layer
│   └── tests/                    # pytest suite (80 tests)
├── database/                     # schema.sql, migrations/, seed*.sql, generate_seed_wc2026.py
└── frontend/                     # Next.js 16 scaffolding — planned, not part of backend-v1.0.0
```

ML models are versioned under `backend/app/ml/models/` (the current
production bundle plus `.bak`/`.prepruning.bak` rollback copies from the
WC2026 retrain). Processed training data lives under
`backend/app/data/processed/`. There is no separate top-level `docs/` or
`scripts/` directory — documentation is individual Markdown files at the
repo root, and one-off data/seed generation scripts live next to the data
they produce (e.g. `database/generate_seed_wc2026.py`).

## Live database validation (2026-07-04)

Raw network access to the live Supabase Postgres project (`<project-ref>`)
became reachable from this dev environment for the first time today. Prior
revisions of this and other docs said the DB was unreachable and that the
WC2026 migration/seed had never been run against a real instance — that was
true when written and is **no longer true**. What was actually verified
against the live database today:

- The WC2026 migration (`database/migrations/002_wc2026_upgrade.sql`) is
  applied: `team_statistics` and `tournament_stages` tables exist, and the
  new `teams`/`matches` columns (`elo_rating`, `fifa_code`, `wc2026_group`,
  `stage_id`, `tournament_year`, `home_xg`/`away_xg`, `external_match_id`,
  `data_source`) are present.
- The database is seeded: `matches` has 419 rows tagged with a non-NULL
  `data_source` (330 `wc_2002_2022_dataset` + 89 `wc_2026_live`), and
  `team_statistics` has 132 rows — matching `DATABASE_SCHEMA.md`'s expected
  counts exactly. (The `matches` table also still holds ~49,389 rows total —
  see the open item below on API scoping.)
- Spot-checked against known football history: **Brazil 2-0 Germany**, 2002
  final (2002-06-30, `stage='final'`), and **Brazil 1-7 Germany**, 2014
  semi-final (2014-07-08, `stage='semi_final'`), are both present in the
  live `matches` table with the correct scorelines, dates, and stages.
- Team names are canonicalized per `teams_reference.csv`'s convention:
  confirmed `Türkiye` (not "Turkey"), `Cabo Verde`, and `USA` (not "United
  States") all exist as the canonical rows in the live `teams` table.
- The backend was booted directly against this live database (not the
  processed CSVs) and exercised end-to-end: `/health`, the Swagger/OpenAPI
  docs at `/docs`, live `POST /predictions/predict` calls across 6 realistic
  matchups, and `POST /tournament/simulate` Monte Carlo runs at 100, 1000,
  and 5000 iterations — all completed successfully.
- Two real bugs were found and fixed during this pass that could not have
  been caught in any earlier session, because they only manifest with the
  DB actually reachable: a missing `data_source IS NOT NULL` filter in
  `backend/app/ml/data/loader.py` (without it, live inference silently pulls
  in the ~49k superseded legacy rows alongside the 419 WC-only rows), and a
  SQLAlchemy column-type mismatch in `backend/app/models/match.py` (id/FK
  columns declared as `String` against native Postgres `uuid` columns,
  which breaks joins with `operator does not exist: uuid = character
  varying`). See `CHANGELOG.md`'s 2026-07-04 validation-pass entry for the
  full list of fixes from this pass.

See `KNOWN_ASSUMPTIONS.md` for one significant open question surfaced by
this validation (public API endpoints not scoped to the WC-only dataset the
way the ML pipeline is) that is a product decision, not a bug.

## Machine Learning Pipeline

Three XGBoost models — two `count:poisson` regressors (home/away expected
goals) and one `multi:softprob` 3-class classifier (home win / draw / away
win) — share a 134-column feature matrix (rolling form at 5/10/20-match
windows, dynamic Elo, FIFA rankings, head-to-head, rest days, knockout
experience, and draw-predictive interaction terms) and one fitted
`StandardScaler`.

- **Training data:** a dedicated WC-only corpus (419 matches: 330 real
  2002–2022 World Cup matches + 89 real 2026 matches), not the earlier
  broad "all competitions 1872–2017" dataset.
- **Validation:** expanding-window walk-forward cross-validation by
  tournament edition (6 folds), not a random shuffle split — chosen because
  team strength drifts across editions and a random split would leak future
  form into training.
- **Hyperparameter search:** Optuna (`TPESampler`), jointly tuning regressor
  params, classifier params, and a draw-class sample-weight multiplier
  against a composite accuracy/draw-recall/MAE objective.
- **Calibration:** isotonic regression and Platt scaling are both fit on the
  validation split; the better one by Brier score is stored and applied at
  inference time.
- **Explainability:** SHAP `TreeExplainer` over the classifier, returning
  top positive/negative feature attributions per prediction.
- **Feature pruning:** a follow-up empirical pass (SHAP, permutation
  importance, correlation, mutual information, variance analysis) removed
  29 of 163 features with verified zero/duplicate signal, landing at the
  current 134.

Full detail, including per-fold metrics and the honest caveats around
training on a small (376-row) dataset: [`MODEL_PIPELINE.md`](MODEL_PIPELINE.md)
and [`MODEL_EVALUATION.md`](MODEL_EVALUATION.md).

## Tournament Simulator

Monte Carlo simulation of the official FIFA World Cup 2026 format — 48
teams, 12 groups of 4, round-robin group stage, then single-elimination from
the Round of 32 through the Final (104 matches total), run across worker
processes via `ProcessPoolExecutor`. Because the real 2026 tournament is
already underway, the simulator substitutes real completed results (read
from the processed match history) for matches that have actually been
played, and only genuinely-unplayed fixtures are Monte Carlo simulated —
including correctly handling knockout matches with a level real regulation
score (extra time/penalties are still simulated from that real scoreline)
and using the real Round-of-32 bracket pairings once the group stage
resolves. See [`TOURNAMENT_ENGINE.md`](TOURNAMENT_ENGINE.md) for the
tiebreak rules, bracket construction, and the bugs that were found and fixed
in this engine.

## API Documentation

Interactive OpenAPI docs are served at `/docs` (and `/redoc`) when
`DEBUG=true`. Full endpoint reference: [`API_DOCUMENTATION.md`](API_DOCUMENTATION.md).

Headline endpoints:

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/predictions/predict` | Run a match prediction (expected goals, probabilities, SHAP explanation) |
| POST | `/api/v1/tournament/simulate` | Monte Carlo tournament simulation, optionally using the real FIFA 2026 groups/results |
| GET | `/api/v1/tournament/2026/groups` | The official 2026 groups (A-L, 48 teams) |
| GET | `/api/v1/tournament/2026/schedule` | The official 104-fixture schedule, filterable by stage/venue |
| GET | `/api/v1/matches/{match_id}` | Match detail, including per-team box-score stats when available |
| GET | `/api/v1/teams/{team_id}/stats` | Full stats for one team |
| GET | `/api/v1/analytics/global` | Aggregate match/goal analytics across history |

## Roadmap / Future Improvements

Pulled from the honest gaps documented across `MODEL_EVALUATION.md`,
`DATABASE_SCHEMA.md`, `DATA_PIPELINE.md`, and `KNOWN_ASSUMPTIONS.md` — not
generic aspirations:

- **Build out and integrate the Next.js frontend.** The backend is frozen at
  `backend-v1.0.0` and validated end-to-end; the frontend under `frontend/`
  has existing scaffolding (pages, components, auth flow) but has not been
  wired up to the validated backend or exercised as part of any test pass.
  This is the next major phase of work, not a same-release deliverable.
- **Decide whether the public API should be WC-only-scoped.** Now that the
  live database is reachable and verified, a real gap has surfaced: `GET
  /api/v1/matches` and `/analytics/dashboard`'s `total_matches_analyzed`
  still query the full `matches` table (~49,389 rows spanning 1872-2026)
  rather than being scoped to `data_source IS NOT NULL` the way the ML
  pipeline now is (`app/ml/data/loader.py`). Is browsing/counting the full
  legacy history an intentional broader feature of the public API, or should
  these endpoints be scoped to the same 419 WC-only rows the model is
  trained on? See `KNOWN_ASSUMPTIONS.md` — flagged there as an open product
  decision, not a bug.
- **Reconcile training vs. inference data sources.** Training currently
  reads `backend/app/data/processed/matches_historical.csv` directly;
  inference reads the Postgres `matches`/`teams` tables, now filtered to
  `data_source IS NOT NULL` so both sides describe the same 419-row WC-only
  corpus — see `DATA_PIPELINE.md` §2.3.
- **Revisit the draw-boost trade-off.** The current `draw_boost` (1.05)
  pushes draw recall to 1.0 at only 0.222 precision — a real trade-off, not
  a clean win, and worth re-tuning once more tournament data exists.
- **Re-run the old-vs-new model comparison properly.** The previous
  broad-dataset model and the new WC-only model have different feature
  schemas, so no apples-to-apples benchmark has actually been run between
  them yet — only a qualitative comparison exists today.
- **Add rate limiting** to public endpoints, especially tournament
  simulation (`n_simulations` up to 100,000 per request).
- **Real by-minute goal-distribution analytics** — `GET
  /matches/analytics/goal-distribution` is currently a documented synthetic
  placeholder (`is_synthetic: true`), since no goal-minute event data exists
  in the schema.
- **Revisit `teams → matches` `ON DELETE CASCADE`.** Flagged as a latent
  data-loss footgun if a team-delete path is ever added; no such endpoint
  exists today, so this is low urgency but unresolved.
- **Expand test coverage** further on the teams/analytics endpoints, and
  consider reconciling the swapped file naming between `test_tournament.py`
  (unit tests) and `test_simulator.py` (HTTP endpoint tests).

## License

MIT — see [`LICENSE`](LICENSE).

## Contributing

This is a personal project, but issues and pull requests are welcome.

- **Bug reports / feature requests:** open a GitHub issue describing the
  problem or proposal, including repro steps for bugs where possible.
- **Pull requests:** fork the repo, create a feature branch, and open a PR
  against `main`. Please keep PRs focused on one change at a time.
- **Before submitting:** run `cd backend && pytest -q` and make sure the
  suite passes; match the existing code style (Pydantic v2 schemas, async
  SQLAlchemy patterns, type hints on new backend code).
- Documentation changes (this README, the per-topic `.md` files at the repo
  root) are just as welcome as code changes — several of the docs in this
  repo exist specifically to keep claims about the system honest and
  verifiable against the actual source.
