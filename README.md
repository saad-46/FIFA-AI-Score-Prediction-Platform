# FIFA AI Score Prediction Platform

An AI-powered platform for predicting FIFA match outcomes and simulating the
FIFA World Cup 2026 tournament. A FastAPI backend serves XGBoost-based match
predictions (expected goals, win/draw/loss probabilities, SHAP explanations)
trained on a dedicated World Cup-only corpus, plus a Monte Carlo tournament
simulator built on the official 48-team, 12-group FIFA World Cup 2026 format
that is aware of real, in-progress 2026 results. A Next.js frontend consumes
the API for match prediction, team analytics, and tournament visualization.

The 2026 tournament is genuinely in progress as this is written, and the
simulator and training data reflect that: real completed 2026 matches are
used as ground truth rather than re-simulated, and the model is trained on
real match data through the current point in the tournament.

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
  FIFA pre-tournament rankings as separate model features.
- **FastAPI backend** — async SQLAlchemy 2.0, Pydantic v2, in-process TTL
  caching (no Redis dependency).
- **Supabase / PostgreSQL** database, with Row Level Security.
- **Next.js 15 frontend** — TypeScript, App Router, Tailwind CSS.

## Screenshots

<!-- Add screenshots here — not yet captured for this release. -->

## Tech Stack

**Backend:** Python 3.12, FastAPI 0.115, Pydantic v2, SQLAlchemy 2.0 (async,
asyncpg), Uvicorn

**Database:** PostgreSQL via Supabase

**ML:** XGBoost 2.1, scikit-learn, pandas, NumPy, SciPy, SHAP, Optuna
(hyperparameter search)

**Frontend:** Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4,
Radix UI, react-hook-form + zod, SWR, Recharts, Supabase JS client

See `backend/requirements.txt` and `frontend/package.json` for exact pinned
versions.

## Architecture

Frontend (Next.js, Vercel) → FastAPI backend (Render) → services layer →
SQLAlchemy async → PostgreSQL (Supabase), with a separate ML layer
(predictor, feature engineering, Poisson engine, SHAP explainer) and a
Monte Carlo tournament engine (`ProcessPoolExecutor`-based) sitting behind
the API routers. See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full
component diagram, request lifecycles, and key design decisions — this
section deliberately doesn't repeat it.

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

> **Note:** as of this writing, none of the WC2026 schema/seed changes above
> have actually been applied to a live Supabase instance — the database was
> unreachable from the environment this upgrade was developed in. The model
> was retrained directly against the processed CSVs under
> `backend/app/data/processed/` instead (see [`DATA_PIPELINE.md`](DATA_PIPELINE.md)).
> If you're setting this up fresh, run the migration/seed above yourself and
> verify the row counts documented in `DATABASE_SCHEMA.md` before relying on
> live predictions matching the retrained model's training data.

### Frontend setup

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
└── frontend/                     # Next.js 16 app (App Router, TypeScript)
```

ML models are versioned under `backend/app/ml/models/` (the current
production bundle plus `.bak`/`.prepruning.bak` rollback copies from the
WC2026 retrain). Processed training data lives under
`backend/app/data/processed/`. There is no separate top-level `docs/` or
`scripts/` directory — documentation is individual Markdown files at the
repo root, and one-off data/seed generation scripts live next to the data
they produce (e.g. `database/generate_seed_wc2026.py`).

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

- **Apply the WC2026 database migration and seed to a live Supabase
  instance.** `database/migrations/002_wc2026_upgrade.sql` and
  `database/seed_wc2026.sql` are hand-reviewed and verified by inspection
  but have never been run against a real database — the sandbox this
  upgrade was built in couldn't reach Supabase. Until this is applied, the
  live `matches`/`teams` tables don't reflect the WC-only training corpus
  the current model was actually trained on.
- **Reconcile training vs. inference data sources.** Training currently
  reads `backend/app/data/processed/matches_historical.csv` directly;
  inference reads the Postgres `matches`/`teams` tables. These are only
  consistent once the seed above has been applied — see `DATA_PIPELINE.md`
  §2.3.
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
