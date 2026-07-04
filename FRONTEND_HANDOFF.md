# FIFA World Cup 2026 AI Prediction Platform — Frontend Handoff

**This document is the complete handoff from the Backend Phase to the Frontend Phase.**
Paste this entire document into a new Claude conversation as the first message. Assume that conversation has zero prior context — everything needed to continue development without asking clarifying questions is below.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Tech Stack](#2-tech-stack)
3. [Project Structure](#3-project-structure)
4. [Backend Status](#4-backend-status)
5. [Database](#5-database)
6. [Machine Learning](#6-machine-learning)
7. [Available APIs](#7-available-apis)
8. [Environment Variables](#8-environment-variables)
9. [Frontend Requirements](#9-frontend-requirements)
10. [UI/UX Goals](#10-uiux-goals)
11. [API Integration Guide](#11-api-integration-guide)
12. [Deployment](#12-deployment)
13. [Testing](#13-testing)
14. [Known Limitations](#14-known-limitations)
15. [GitHub](#15-github)
16. [Frontend Development Roadmap](#16-frontend-development-roadmap)
17. [Claude Instructions](#17-claude-instructions)
18. [Final Summary](#18-final-summary)

---

## 1. Project Overview

**Project name:** FIFA AI Score Prediction Platform

**Purpose:** An AI-powered web application that predicts FIFA World Cup 2026 match outcomes (expected goals, win/draw/loss probabilities, most-likely scorelines) and simulates the entire 48-team tournament via Monte Carlo simulation, producing a probability of each team reaching every stage up to and including winning the tournament.

**Problem being solved:** Football score prediction is normally either (a) pure gut-feel/punditry with no quantified uncertainty, or (b) generic betting-odds aggregation with no explainability. This project builds a from-scratch ML pipeline (XGBoost regressors + classifier, dynamic Elo ratings, FIFA rankings, SHAP explainability) trained specifically on World Cup-era football, then wraps it in a real, usable product: a prediction API, a tournament simulator that understands the actual 2026 format and the actual real-world state of the in-progress tournament, and (once this phase is done) a polished web frontend.

**End goal:** A complete, deployed web app where a user can look up any two national teams and get an AI prediction with a full explanation, browse the official FIFA World Cup 2026 schedule and groups, run/browse Monte Carlo tournament simulations, see analytics dashboards, and (if authenticated) save predictions and track their own prediction accuracy over time.

**Why this project exists:** Originally scoped as a general international-football predictor, the project was deliberately re-scoped mid-development to focus exclusively on the FIFA World Cup 2026 tournament — training data, tournament logic, and UX should all be WC2026-specific, not generic "predict any football match" functionality.

**Target users:** Football fans following the 2026 World Cup who want data-driven predictions and tournament outlooks; a secondary audience is this project's own portfolio/demonstration value (it showcases a full ML + backend + (soon) frontend product built end-to-end).

**Current project status:** **The backend is 100% complete, fully validated against live production infrastructure, and frozen at git tag `backend-v1.0.0`.** Frontend work has *some* existing scaffolding (see [Section 3](#3-project-structure) and [Section 9](#9-frontend-requirements)) but it was built against an earlier iteration of the API contract and needs reconciliation before any new feature work — this is not a blank slate, but it is not production-ready either.

**Overall architecture:**

```
┌─────────────────────┐        ┌──────────────────────────┐        ┌─────────────────────┐
│   Next.js Frontend   │  HTTP  │     FastAPI Backend       │  SQL   │  Supabase Postgres   │
│  (Vercel, planned)   │───────▶│  (Render, backend-v1.0.0)  │───────▶│   (live, verified)   │
│  React 19 + TS       │◀───────│  async SQLAlchemy 2.0      │◀───────│  RLS-secured, 419    │
└─────────────────────┘  JSON   │  + XGBoost ML layer        │  rows  │  WC-only matches     │
                                 │  + Monte Carlo simulator   │        └─────────────────────┘
                                 └──────────────────────────┘
                                            │
                                 Supabase Auth (JWT, HS256)
                                 verified directly by the
                                 backend — no separate auth
                                 service
```

The backend is a monolith (one FastAPI app, no microservices), with three internal layers: **API routers** (`app/api/v1/endpoints/`) → **services** (`app/services/`, business logic + DB queries) → **ML layer** (`app/ml/`, prediction/training/simulation, entirely separate from the request/response cycle except for a 6-hour in-process DataFrame cache). Auth is Supabase's own (JWT issued by Supabase Auth, verified by the backend using the shared JWT secret — the backend never talks to a separate "auth service").

---

## 2. Tech Stack

### Backend (complete, frozen)
| Component | Technology | Version |
|---|---|---|
| Language | Python | 3.12 |
| Web framework | FastAPI | 0.115.5 |
| Validation | Pydantic | v2 |
| ORM | SQLAlchemy | 2.0.36 (async) |
| DB driver | asyncpg | 0.30.0 |
| ASGI server | Uvicorn | — |
| ML | XGBoost | 2.1.3 |
| ML utils | scikit-learn, pandas, NumPy, SciPy | — |
| Explainability | SHAP | — |
| Hyperparameter search | Optuna | — |
| Auth | PyJWT | 2.12.1 |
| Testing | pytest, pytest-asyncio, httpx (test client) | — |

### Database
| Component | Technology |
|---|---|
| Database | PostgreSQL 17.6 |
| Hosting | Supabase (project already provisioned and live) |
| Security | Row Level Security (RLS) on every table |
| Auth provider | Supabase Auth (issues the JWTs the backend verifies) |

### Frontend (existing scaffold — see Section 3 for exact state)
| Component | Technology | Version |
|---|---|---|
| Framework | Next.js | 16.2.6 (App Router) |
| UI library | React | 19.2.4 |
| Language | TypeScript | 5 |
| Styling | Tailwind CSS | 4 |
| Component primitives | Radix UI | various (`@radix-ui/react-*`) |
| Forms | react-hook-form + zod + @hookform/resolvers | — |
| HTTP client | axios | 1.16.1 |
| Data fetching/caching | SWR | 2.4.1 |
| Charts | Recharts | 3.8.1 |
| Auth/DB client | @supabase/supabase-js, @supabase/ssr, @supabase/auth-helpers-nextjs | 2.106.0 / 0.10.3 / 0.15.0 |
| Animation | Framer Motion | 12.39.0 |
| Icons | lucide-react | 1.16.0 |
| Dates | date-fns | 4.2.1 |
| Theming | next-themes | 0.4.6 |

**Important note:** the existing scaffold has *two parallel auth mechanisms* present at once — a manual `localStorage`-based JWT + axios-interceptor pattern (`lib/api/client.ts`) **and** a full Supabase SSR/auth-helpers setup (`lib/supabase/{client,middleware,server}.ts`, plus `app/auth/*` routes). These need to be reconciled into one coherent pattern early in frontend work — see [Section 17](#17-claude-instructions).

### Deployment
| Layer | Platform | Status |
|---|---|---|
| Backend | Render | Configured (`backend/render.yaml`), CORS origin placeholder needs the real Vercel domain before going live |
| Frontend | Vercel | Not yet deployed |
| Database | Supabase | Live, active, verified |

### CI/CD
**None currently exists.** No GitHub Actions workflows, no automated test-on-PR, no automated deploy pipeline. This is a real gap — see [Section 14](#14-known-limitations) and consider it early in the roadmap.

---

## 3. Project Structure

```
fifa-score-predictor/                    (repo root)
├── README.md                            Project overview, setup, status
├── LICENSE                              MIT
├── CHANGELOG.md                         Full dated history of every change
├── ARCHITECTURE.md                      System design / component diagram
├── API_DOCUMENTATION.md                 Endpoint reference (see Section 7 below for the authoritative live version)
├── DATABASE_SCHEMA.md                   Full schema + design rationale
├── DATA_PIPELINE.md                     Raw data → processed data → DB flow
├── MODEL_PIPELINE.md                    Training pipeline details
├── MODEL_EVALUATION.md                  Full model evaluation report + metrics
├── FEATURE_ENGINEERING.md               Every feature, added/removed, with evidence
├── ELO_SYSTEM.md                        Dynamic Elo design + the inference-time fix
├── RANKINGS_INTEGRATION.md              FIFA ranking integration design
├── TOURNAMENT_ENGINE.md                 Monte Carlo simulator design
├── TRAINING_GUIDE.md                    How to (re)run training
├── KNOWN_ASSUMPTIONS.md                 Every documented assumption/open item (READ THIS)
│
├── backend/                             ⚠️ DO NOT MODIFY except to fix a genuine bug
│   ├── app/
│   │   ├── main.py                      FastAPI app, lifespan (DB connect on startup), CORS middleware
│   │   ├── api/v1/
│   │   │   ├── router.py                Combines all 5 endpoint routers
│   │   │   └── endpoints/               predictions.py, teams.py, matches.py, analytics.py, tournament.py
│   │   ├── core/
│   │   │   ├── config.py                Settings (env vars) — see Section 8
│   │   │   ├── security.py              Supabase JWT verification
│   │   │   └── cache.py                 In-process TTL cache decorator (no Redis in this stack)
│   │   ├── data/
│   │   │   ├── fifa_2026/               Official 2026 groups/schedule/venues (static JSON, trusted source of truth)
│   │   │   └── processed/               matches_historical.csv, teams_reference.csv, match_team_stats.csv — the actual ML training corpus
│   │   ├── db/                          SQLAlchemy async engine/session setup
│   │   ├── ml/                          Training, feature engineering, prediction, tournament simulation — see Section 6
│   │   ├── models/match.py              SQLAlchemy ORM models — the single source of truth for DB schema in code
│   │   ├── schemas/                     Pydantic v2 request/response models — see Section 7
│   │   ├── services/                    Business logic + DB queries, one file per domain
│   │   └── tests/                       80 tests, all passing
│   ├── render.yaml                      Render deployment config
│   ├── requirements.txt
│   └── .env.example                     Template — copy to .env, never commit .env
│
├── database/                            ⚠️ DO NOT MODIFY — schema is live and frozen
│   ├── schema.sql                       Full DDL (fresh-install target state)
│   ├── migrations/002_wc2026_upgrade.sql  Additive migration (existing DB → target state)
│   ├── seed_wc2026.sql                  Generated seed data (72 teams, 419 matches, 132 stats rows)
│   ├── seed.sql                         Superseded broader dataset — optional, not required
│   └── generate_seed_wc2026.py          The script that generated seed_wc2026.sql from the processed CSVs
│
├── frontend/                             ✅ THIS IS YOUR WORKSPACE
│   ├── src/
│   │   ├── app/
│   │   │   ├── (app)/                   Authenticated app shell: dashboard, predict, matches, teams, teams/[id], tournaments, analytics, saved
│   │   │   ├── (marketing)/page.tsx     Public landing page
│   │   │   ├── auth/                    login, register, callback, signout, verify-email
│   │   │   └── layout.tsx, page.tsx, globals.css
│   │   ├── components/
│   │   │   ├── analytics/               goal-distribution-chart, stats-card, win-probability-chart
│   │   │   ├── layout/                  navbar, footer
│   │   │   ├── matches/                 match-card
│   │   │   ├── predictions/             prediction-form, prediction-result
│   │   │   ├── teams/                   team-card
│   │   │   └── ui/                      badge, button, card, input, label, progress, select, separator, skeleton, tabs, toast, toaster (Radix-based primitives)
│   │   ├── hooks/                       use-debounce, use-toast
│   │   ├── lib/
│   │   │   ├── api/                     client.ts, predictions.ts, teams.ts, matches.ts, analytics.ts — **no tournament.ts yet, needs creating**
│   │   │   ├── supabase/                client.ts, middleware.ts, server.ts (SSR auth helpers)
│   │   │   └── utils.ts
│   │   ├── types/index.ts               TypeScript interfaces — **stale, missing new backend fields, needs updating**
│   │   └── middleware.ts
│   ├── package.json
│   ├── .env.local.example
│   └── vercel.json
│
└── .github/                              Does not currently contain workflows — CI/CD gap
```

### Folders you must NOT modify during frontend work
- **`backend/`** — frozen at `backend-v1.0.0`. Only touch this if you discover an actual bug that blocks frontend integration (e.g. a genuine 500, a schema mismatch) — and if you do, document exactly why in your commit message.
- **`database/`** — schema is live and matches the frozen backend. Do not add/alter tables, columns, or migrations.
- Any of the root-level `.md` documentation files listed above — they document the frozen backend state. If something in them is factually wrong, that's worth a note back to the project owner, not a silent edit.

---

## 4. Backend Status

Everything below is **done, tested, and verified against the live production Supabase database** (not mocks) as of `backend-v1.0.0`:

- ✓ **FastAPI** — 26 endpoints across 5 routers, full async request lifecycle, fails loudly (refuses to boot) rather than serving traffic if the database is unreachable at startup.
- ✓ **Supabase** — live project, confirmed reachable, schema applied, fully seeded (419 WC-only matches, 48 fully-populated 2026 teams + historical teams), RLS enabled and correctly scoped on every table.
- ✓ **Database** — normalized schema, zero duplicate teams, zero duplicate matches, zero orphaned foreign keys (independently re-verified multiple times this session).
- ✓ **Models** — SQLAlchemy ORM (`app/models/match.py`) matches the live schema exactly, including a same-day fix for a native-`uuid`-vs-`String` column type mismatch that had been silently broken since the schema was first designed.
- ✓ **Prediction Engine** — two XGBoost regressors (home/away expected goals, `count:poisson` objective) + one XGBoost classifier (win/draw/loss, `multi:softprob`), 134 features (post empirical pruning from 163), isotonic-calibrated probabilities, SHAP explainability on every prediction.
- ✓ **Elo** — dynamic, tournament-weighted Elo ratings, computed over the full match history and (as of this session) **correctly wired into live inference**, not just training — this was a real bug (`elo_difference` silently stuck at a constant `0.0` for every live prediction) found and fixed this session.
- ✓ **Tournament Simulator** — Monte Carlo simulation of the real 48-team/12-group FIFA 2026 bracket, aware that the 2026 tournament is genuinely in progress: matches already played use their real recorded result instead of being re-simulated; only genuinely future matches go through Monte Carlo.
- ✓ **Analytics** — dashboard stats, global analytics, model metrics, feature importance, all live and tested.
- ✓ **Authentication** — Supabase JWT (HS256) verified server-side using the shared JWT secret; `/predictions/predict` is intentionally public (stateless, no user data), save/list/delete/accuracy endpoints require auth.
- ✓ **Testing** — **80/80 backend tests passing**, run repeatedly throughout this session with zero regressions in the final state.
- ✓ **Documentation** — the full doc set listed in Section 3, all updated this session to reflect the live-verified reality (several were previously written under the assumption the database was unreachable — that's since been corrected everywhere it mattered).

**Backend version: `backend-v1.0.0`** (git tag, annotated, pushed to `origin/main`). **The backend is feature-frozen.** Do not add new backend endpoints, do not change ML behavior, do not alter the database schema, unless you discover a genuine bug that blocks frontend integration — and even then, keep the fix as narrow as possible and document it clearly.

---

## 5. Database

Live Supabase Postgres, 7 tables, all with RLS enabled.

### `teams`
The team roster — both the 48 real 2026 World Cup teams and historical-only teams that appear in older match records.

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` (PK) | |
| `name` | `varchar(100)`, unique | Canonical name (e.g. `Türkiye` not `Turkey`, `USA` not `United States`, `Cabo Verde` not `Cape Verde`) |
| `country` | `varchar(100)` | |
| `confederation` | `varchar(50)`, nullable | |
| `fifa_ranking` | `int`, nullable | Current/most-recent FIFA world ranking |
| `elo_rating` | `smallint`, nullable | Elo snapshot — **NULL for historical-only teams not in the 2026 field** (never fabricated) |
| `fifa_code` | `varchar(3)`, nullable | 3-letter FIFA code (e.g. `MEX`) — populated only for the 48 2026 teams |
| `wc2026_group` | `char(1)`, nullable | Group letter A–L — populated only for the 48 2026 teams |
| `ranking_updated_at` | `timestamptz`, nullable | Auto-maintained by a DB trigger whenever `fifa_ranking`/`elo_rating` changes |
| `logo_url`, `founded_year`, `home_stadium` | nullable | Not currently populated with real data — placeholders for future use |
| `created_at`, `updated_at` | `timestamptz` | |

### `matches`
| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` (PK) | |
| `date` | `date` | |
| `home_team_id` | `uuid` (FK → teams.id), NOT NULL | |
| `away_team_id` | `uuid` (FK → teams.id), **nullable** | A small number of knockout fixtures have a genuinely unresolved opponent (e.g. a WC2026 Round-of-16 TBD slot) — this is real, not a bug. **The frontend must handle `away_team`/`away_team_id` being null.** |
| `home_score`, `away_score` | `int`, nullable | Null for not-yet-played matches |
| `tournament` | `varchar(200)` | e.g. `"FIFA World Cup 2026"` |
| `stage` | `varchar(100)`, nullable | Free-text stage name |
| `stage_id` | `smallint` (FK → tournament_stages.stage_id), nullable | Normalized stage reference |
| `tournament_year` | `smallint`, nullable | |
| `neutral_venue` | `boolean` | |
| `city`, `country` | `varchar`, nullable | Often null for historical rows |
| `home_xg`, `away_xg` | `numeric(4,2)`, nullable | Only populated for 2026-era matches; historical rows genuinely have no xG data |
| `external_match_id` | `varchar(50)`, nullable | Traceability back to the source CSV |
| `data_source` | `varchar(50)`, nullable | **Important**: `'wc_2002_2022_dataset'` / `'wc_2026_live'` for the 419-row WC-only corpus, `NULL` for ~49,000 rows of a superseded broader dataset still sitting in this table (see [Known Limitations](#14-known-limitations)) |
| `status` | `varchar(20)` | `'scheduled'` / `'live'` / `'completed'` |

### `team_statistics`
Per-match, per-team box-score stats (possession, shots, corners, fouls, offsides, saves, player of the match). Grain: one row per `(match_id, team_id)`. Only covers 66 of the 419 WC-only matches (2026 matches only) — a documented, real gap, not a bug.

### `tournament_stages`
Static 7-row lookup: `stage_id, stage_key, stage_name, is_knockout, sort_order`.

### `profiles`
Extends Supabase's own `auth.users` — `id` (FK to `auth.users.id`), `full_name`, `avatar_url`, `role` (`user`/`admin`), timestamps.

### `saved_predictions`
A user's saved predictions. Key columns: `id`, `user_id` (references `auth.users.id`, not modeled as an ORM relationship since `auth.users` lives in Supabase's own schema), `prediction_id`, `home_team`, `away_team`, `predicted_home_score`, `predicted_away_score`, three outcome probabilities, `home_expected_goals`/`away_expected_goals` **(note: the live DB's actual column names are `home_expected_goals`/`away_expected_goals`; the ORM's Python attribute names are `expected_home_goals`/`expected_away_goals` — this is an intentional SQLAlchemy column-name override fixed this session, not something to "fix" again)**, `confidence_score`, `model_version`, `actual_home_score`/`actual_away_score`/`was_correct` (populated later once a real result is known, for accuracy tracking).

### `tournament_results`
Actual results as they occur, one row per schedule fixture — currently unpopulated (0 rows), exists for future use.

### Relationships
`matches.home_team_id`/`away_team_id` → `teams.id` (CASCADE delete — flagged as a latent footgun in `KNOWN_ASSUMPTIONS.md`, not yet changed). `team_statistics.match_id`/`team_id` → `matches.id`/`teams.id` (RESTRICT delete). `matches.stage_id` → `tournament_stages.stage_id` (RESTRICT delete).

### RLS
Every table has RLS enabled. Public reference data (`teams`, `matches`, `tournament_stages`, `team_statistics`) allows public `SELECT`. `profiles` and `saved_predictions` are scoped to `auth.uid() = id` / `auth.uid() = user_id` — a user cannot see or modify another user's rows via PostgREST. **Note**: the actual backend does NOT connect through PostgREST/RLS — it connects via a direct `postgres.<project>` role through SQLAlchemy, which bypasses RLS entirely (same trust level as `service_role`). Per-user data isolation is enforced at the **application layer** (explicit `WHERE user_id == ...` filters in `app/services/`), not by RLS. This is documented, intentional, and already verified correct — but it means any new backend code touching `saved_predictions` must include that filter explicitly; RLS will not save you. (You should not be writing new backend code per Section 4, but it's important context if you ever query the DB directly from a server-side Next.js route.)

**What the frontend needs to know practically:** query the REST API (Section 7), not the database directly, for everything except perhaps using the Supabase JS client for auth session management. Never assume `away_team` is non-null on a `Match` object. Never assume every team has `elo_rating`/`fifa_code`/`wc2026_group` populated (only the 48 2026 teams do).

---

## 6. Machine Learning

**Training pipeline** (`backend/app/ml/train.py`): loads the processed WC-only corpus (`matches_historical.csv`, 419 rows: 330 real World Cup matches 2002–2022 + 89 real in-progress 2026 matches), builds a feature vector per match (skipping the first `MIN_HISTORY=30` rows since rolling-window features need prior history), splits chronologically via **expanding-window walk-forward cross-validation by tournament edition** (not a random 70/30 split — explicitly chosen because football has real temporal drift and the dataset is small enough that a single random split would be too noisy to trust), trains two XGBoost regressors + one XGBoost classifier, fits probability calibrators (isotonic beat Platt scaling on Brier score), and saves the model bundle + several JSON reports.

**Feature engineering** (`backend/app/ml/features/feature_engineering.py`): **134 features** after an empirical pruning pass removed 29 of an original 163 (21 exact algebraic duplicates, 2 true zero-variance constants, 6 confirmed-zero-importance features — full evidence in `FEATURE_ENGINEERING.md`). Feature categories: rolling team form (last 5/10/20 matches — attack/defense strength, momentum, goal volatility, unbeaten/win/conceding streaks), head-to-head history, **dynamic Elo difference** (top-3 most important feature, and the one that was silently broken at inference until this session), **FIFA ranking difference** (complementary to Elo, not a replacement — sourced from `teams_reference.csv`, kept as a genuinely swappable data source, not hardcoded), **knockout experience** (prior Round-of-32+ appearances per team), home advantage / neutral venue, confederation match, rest days between matches, expected-goals-based features.

**Model type:** `home_model`/`away_model` are `XGBRegressor` (`count:poisson` objective — appropriate for count data like goals), `result_model` is `XGBClassifier` (`multi:softprob`, class-weighted + optionally draw-boosted).

**Dataset:** WC-only, 419 rows total, 406 completed (13 not-yet-played 2026 fixtures excluded from training). This is a genuinely small dataset for a 134-feature model — every metric in `MODEL_EVALUATION.md` carries wide standard errors; treat model outputs as directionally informative, not laboratory-precise. This is an intentional, documented tradeoff (narrow-but-relevant WC-only data vs. broad-but-less-relevant all-competitions data) — not something to silently "fix" by retraining on more data.

**Prediction flow** (`backend/app/ml/models/predictor.py`, called by `POST /predictions/predict`): build the feature vector for the requested matchup → scale it → run both regressors to get expected goals → run a Poisson score-matrix simulation over the expected goals to get a full scoreline probability distribution → run the classifier to get calibrated win/draw/loss probabilities → **blend the Poisson-derived and classifier-derived outcome probabilities 60/40** → run SHAP to get the top positive/negative feature attributions → attach head-to-head stats and a few auto-generated "insights" → return everything as one `PredictionResult`.

**Confidence calculation:** derived from how decisively the blended probabilities favor one outcome (not a separate model) — see `prediction_service.py` if you need the exact formula; not something the frontend needs to recompute, it's returned directly as `confidence_score`.

**Poisson model:** given predicted expected goals for both teams, computes a full scoreline probability matrix (e.g. P(1-0), P(2-1), etc.) using independent Poisson distributions per team — this is what produces `top_scorelines` and `most_likely_score`.

**Elo:** computed once per 6-hour cache refresh (`app/ml/data/loader.py`), chronologically, tournament-weighted (World Cup matches count more than friendlies in the rating updates), with strict `<` date filtering so a match's own result can never leak into its own Elo inputs.

**Monte Carlo tournament simulation** (`backend/app/ml/tournament_simulator.py`, called by `POST /tournament/simulate`): runs N simulations (default 10,000, configurable 100–100,000) of the full 48-team bracket using the trained predictor for every hypothetical matchup, with two important real-world-awareness features: (1) matches from the actual, in-progress 2026 tournament that have already been played use their **real recorded score**, not a simulated one; (2) the actual resolved Round-of-32 bracket (pulled from the official schedule once group stage results are known) is used instead of the simulator's own bracket-pairing heuristic when it would match reality. Runs in a background thread (`asyncio.to_thread`) since it's CPU-bound.

**What each prediction API response tells the frontend:** every field on `PredictionResult` (Section 7) is meaningful and should probably be surfaced somewhere in the UI — this is a rich response, not a bare score guess.

---

## 7. Available APIs

**Base URL (local dev):** `http://localhost:8000/api/v1`
**Interactive docs:** `http://localhost:8000/docs` (Swagger UI, gated behind `DEBUG=true`)
**Health check (no prefix):** `GET /health` → `{"status": "healthy", "version": "1.0.0", "model_loaded": true, "environment": "production"}`

All request/response bodies are JSON. All list endpoints return arrays or a paginated envelope (documented per-endpoint below). All errors follow FastAPI's standard shape: `{"detail": "human-readable message"}` with the appropriate HTTP status code.

### Predictions (`/predictions`)

#### `POST /predictions/predict`
- **Purpose:** Run an AI prediction for a matchup.
- **Auth:** None required (public). If an auth token IS supplied, it's accepted but doesn't change the response.
- **Request body:**
  ```json
  {
    "home_team": "Brazil",
    "away_team": "Argentina",
    "tournament": "FIFA World Cup",
    "neutral_venue": true
  }
  ```
  `home_team`/`away_team`: required strings, 2–100 chars, must differ (case-insensitive). `tournament`: optional string. `neutral_venue`: optional bool, default `false`.
- **Response (200):**
  ```json
  {
    "prediction_id": "319cf3b5-76e1-4b55-b29f-35f104463fab",
    "home_team": "Brazil",
    "away_team": "Argentina",
    "predicted_home_score": 1,
    "predicted_away_score": 1,
    "expected_home_goals": 1.008,
    "expected_away_goals": 0.474,
    "home_win_probability": 0.481,
    "draw_probability": 0.319,
    "away_win_probability": 0.200,
    "most_likely_score": "1-0",
    "top_scorelines": [
      {"score": "1-0", "probability": 0.1294},
      {"score": "0-0", "probability": 0.093}
    ],
    "prediction_explanation": {
      "predicted_outcome": "Home Win",
      "confidence": 0.581,
      "top_positive_features": [{"feature": "attack_diff_10", "readable_name": "Attack Diff (Past 10 Matches)", "impact": 0.0021}],
      "top_negative_features": [{"feature": "goal_diff_diff_10", "readable_name": "Goal Diff Diff (Past 10 Matches)", "impact": -0.0010}]
    },
    "confidence_score": 0.581,
    "model_version": "1.0.0",
    "insights": [],
    "head_to_head": {
      "total_matches": 0, "home_team_wins": 0, "away_team_wins": 0,
      "draws": 0, "home_team_goals": 0, "away_team_goals": 0
    },
    "created_at": "2026-07-04T08:23:24.160762Z"
  }
  ```
  Note: `head_to_head` correctly returns all-zero when two teams genuinely have never met in the WC-only corpus (e.g. Brazil vs Argentina have literally never met at a World Cup finals in 2002–2026) — this is real data, not a bug. `insights` is currently often an empty array — the auto-generated-insight feature exists but doesn't always produce content; don't rely on it being populated.
- **Common errors:** `422` (validation — missing/too-short team names, teams identical), `500` with generic "Prediction failed" detail (rare, indicates an unknown-team-name edge case or backend issue — report it if you see it).

#### `POST /predictions/{prediction_id}/save`
- **Auth:** Required (Bearer JWT).
- **Purpose:** Persist a prediction (identified by the `prediction_id` returned from `/predict`, cached server-side) to the user's account.
- **Response (201):** `SavedPredictionResponse` — same shape as the saved fields of `PredictionResult` plus `id`, `user_id`, `created_at`, `actual_home_score`/`actual_away_score`/`was_correct` (null until a real result is recorded).
- **Common errors:** `404` if `prediction_id` wasn't found/expired in the server cache (predictions must be saved reasonably soon after being generated — re-run `/predict` if this happens), `401` if not authenticated.

#### `GET /predictions/saved?page=1&page_size=20`
- **Auth:** Required.
- **Response (200):** `SavedPredictionResponse[]` (plain array, **not** wrapped in a pagination envelope — page/page_size just control offset/limit).

#### `DELETE /predictions/saved/{prediction_id}`
- **Auth:** Required.
- **Response:** `204 No Content` on success.
- **Common errors:** `404` if not found, malformed ID, or belongs to another user.

#### `GET /predictions/accuracy`
- **Auth:** Required.
- **Response (200):** `{"total": 12, "correct": 8, "accuracy": 0.6667}` — computed only over saved predictions where `was_correct` has been populated (i.e., the real match has since been played and recorded).

### Teams (`/teams`)

#### `GET /teams/search?q=braz`
Public. `q` required, min 2 chars. Returns `TeamResponse[]` (see shape below), matched by case-insensitive substring on team name.

#### `GET /teams/top?limit=10&tournament=...`
Public. Returns `TeamStatsResponse[]`, sorted by win rate descending, minimum 2 matches played to qualify (recalibrated this session — was previously 10, unreachable given the small WC-only dataset).

#### `GET /teams/head-to-head?home_team_id=<uuid>&away_team_id=<uuid>`
Public. Returns `HeadToHeadResponse`. Malformed (non-UUID) IDs return an all-zero response rather than erroring.

#### `GET /teams/{team_id}`
Public. Returns a single `TeamResponse`:
```json
{
  "id": "50bb82b7-1c79-4f59-8cad-38ea8faf1904",
  "name": "Argentina", "country": "Argentina", "confederation": "CONMEBOL",
  "fifa_ranking": 1, "logo_url": null, "founded_year": null, "home_stadium": null,
  "elo_rating": 2100, "fifa_code": "ARG", "wc2026_group": "D",
  "ranking_updated_at": "2026-06-01T00:00:00Z",
  "created_at": "2026-05-19T18:26:05Z"
}
```
`404` if not found or ID is malformed.

#### `GET /teams/{team_id}/stats?tournament=...&years=...`
Public. Returns `TeamStatsResponse` (matches_played, wins, draws, losses, goals_scored, goals_conceded, goal_difference, win_rate, avg_goals_scored, avg_goals_conceded, clean_sheets, form: last-5 W/D/L array). `404` if team not found.

#### `GET /teams/{team_id}/trend?months=24`
Public. Returns `PerformanceTrendPoint[]` — monthly aggregated wins/draws/losses/goals.

### Matches (`/matches`)

#### `GET /matches?page=1&page_size=20&team=...&tournament=...&year=...&from_date=YYYY-MM-DD&to_date=YYYY-MM-DD`
Public. Returns `PaginatedMatchResponse`:
```json
{
  "data": [ /* MatchResponse[] */ ],
  "total": 49389,
  "page": 1, "page_size": 20, "total_pages": 2470
}
```
**⚠️ Important, currently unresolved:** `total` here reflects the **full historical dataset (~49,389 rows)**, not just the 419-row WC-only corpus the ML pipeline uses — see [Known Limitations](#14-known-limitations). Don't be surprised by a much larger number here than elsewhere in the app.
Each `MatchResponse` includes nested `home_team`/`away_team` objects (dicts, not full `TeamResponse` shape) — `away_team` **can be `null`** (see Section 5).

#### `GET /matches/tournaments`
Public. Returns `string[]` of every distinct tournament name in the dataset.

#### `GET /matches/tournaments/{tournament}/stats`
Public. Returns `TournamentStatsResponse` (total_matches, total_goals, avg_goals_per_match, home/draw/away rates, top_scoring_team, most_goals_in_match).

#### `GET /matches/analytics/goal-distribution?tournament=...`
Public. Returns `GoalDistributionPoint[]`. **Every point currently has `is_synthetic: true`** — this endpoint is a documented placeholder (no goal-minute-level data exists in the DB yet). Surface this honestly in the UI (e.g. a "sample data" badge) rather than presenting it as real.

#### `GET /matches/analytics/scorelines?tournament=...`
Public. Returns `ScorelineFrequency[]` (real data, not synthetic) — most common scorelines with counts/percentages.

#### `GET /matches/{match_id}`
Public. Returns `MatchDetailResponse` (extends `MatchResponse` with a `team_statistics: TeamStatisticsResponse[]` array — often just 1–2 entries or empty, since only 66 of 419 matches have box-score data). `404` if not found or malformed ID.

### Analytics (`/analytics`)

#### `GET /analytics/dashboard`
Auth optional (richer response if authenticated). Returns `DashboardStatsResponse`: `total_predictions`, `accuracy_rate`, `total_matches_analyzed` (⚠️ same full-dataset-count caveat as `/matches` above), `total_teams`, `recent_predictions` (only if authenticated), `top_teams`, `upcoming_matches`.

#### `GET /analytics/global`
Public, cached 60s server-side. Returns `GlobalAnalyticsResponse`: total_matches, total_goals, avg_goals_per_match, home/draw/away win rates, goals_by_year, top_tournaments. **Same full-dataset caveat.**

#### `GET /analytics/model-metrics`
Public. Returns `ModelMetricsResponse`: accuracy, mae, rmse, last_trained, training_samples, model_version — read directly from the training pipeline's saved reports.

#### `GET /analytics/feature-importance`
Public. Returns `FeatureImportanceResponse`: sorted list of `{feature, importance}` plus model_version/total_features. `404` if the model hasn't been trained (shouldn't happen in this frozen release).

### Tournament (`/tournament`)

#### `GET /tournament/2026/groups`
Public. Returns `Fifa2026GroupsResponse` — the official 12 groups (A–L), each with exactly 4 `{code, name}` team entries. No manual input needed; this is the actual official 2026 draw.

#### `GET /tournament/2026/schedule?stage=...&venue_city=...`
Public. Returns `Fifa2026ScheduleResponse` — all 104 official fixtures (or filtered by stage/city). Each match has `match_number`, `date`, `kickoff_time_et`, `venue_city`, `stage`, `group` (group-stage only), `home_team`/`away_team` (team code, or a placeholder like `"W53"`/`"L101"` for still-undetermined knockout slots), and `uncertain` (true if inferred rather than read directly off the official chart — rare, documented).

#### `POST /tournament/simulate`
Public. **This is the expensive one** — request body:
```json
{
  "use_fifa_2026_groups": true,
  "n_simulations": 10000,
  "use_real_results": true
}
```
(Omit `groups`/`use_fifa_2026_groups: false` only if you want a fully custom hypothetical bracket — 48 teams across exactly 12 groups of 4, no duplicates, validated server-side.) `n_simulations`: 100–100,000. Takes roughly 5–9 seconds regardless of `n_simulations` in this range (fixed multiprocessing-pool-spawn overhead dominates, not simulation count — don't expect linear scaling).
**Response (200):**
```json
{
  "probabilities": {
    "ARG": {"group": 1.0, "r32": 0.92, "r16": 0.71, "qf": 0.45, "sf": 0.28, "third_place": 0.03, "final": 0.15, "winner": 0.09},
    "...": { }
  }
}
```
Keyed by **3-letter FIFA team code** (not full team name), one entry per all 48 teams. All 8 probability fields are cumulative-stage-reached probabilities; `winner` values across all 48 teams sum to ~1.0.
**Common errors:** `503` if the model isn't loaded or the simulation couldn't produce a trustworthy result (very rare), `500` on unexpected failure.

---

## 8. Environment Variables

### Backend (`backend/.env`, copy from `backend/.env.example`)
| Variable | Purpose |
|---|---|
| `APP_NAME`, `APP_VERSION` | Metadata, no functional effect |
| `DEBUG` | Gates `/docs`/`/redoc` Swagger UI and SQLAlchemy echo logging — must be `false` in real production |
| `ENVIRONMENT` | `development`/`production` — informational |
| `ALLOWED_ORIGINS` | JSON array of allowed CORS origins — **must include your deployed frontend's real Vercel URL**, not the current placeholder |
| `SUPABASE_URL` | Your Supabase project's REST URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-side-only secret, full DB access — **never expose to frontend** |
| `SUPABASE_ANON_KEY` | Public-safe anon key |
| `SUPABASE_JWT_SECRET` | Used to verify Supabase-issued JWTs server-side |
| `DATABASE_URL` | Direct Postgres connection string (SQLAlchemy) |
| `MODEL_PATH`, `SCALER_PATH`, `FEATURE_IMPORTANCE_PATH` | Paths to the trained model bundle files |
| `MODEL_VERSION` | Version string surfaced in API responses |
| `RATE_LIMIT_PER_MINUTE` | Defined but **not currently enforced anywhere** — no rate-limiting middleware exists (see Known Limitations) |

### Frontend (`frontend/.env.local`, copy from `frontend/.env.local.example`)
| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Public Supabase project URL (safe to expose — `NEXT_PUBLIC_` prefix means it's bundled client-side) |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Public anon key (safe to expose) |
| `NEXT_PUBLIC_API_URL` | Backend API base URL, e.g. `http://localhost:8000/api/v1` locally, the real Render URL in production |
| `NEXT_PUBLIC_APP_URL` | The frontend's own public URL (used for auth redirect callbacks, etc.) |

### Deployment-specific
- **Render** (`backend/render.yaml`): sets `ENVIRONMENT=production`, `DEBUG=false` correctly, but `ALLOWED_ORIGINS` is still a placeholder (`your-app.vercel.app`) — must be updated to the real frontend domain before/during frontend deployment.
- **Vercel** (`frontend/vercel.json`): security headers configured (X-Content-Type-Options, X-Frame-Options, etc.), no environment-variable-specific config there — those are set in the Vercel dashboard.

**Never commit `.env` or `.env.local`** — both are gitignored; only the `.example` templates (placeholders only) are tracked.

---

## 9. Frontend Requirements

The existing scaffold (Section 3) already has route stubs for most of what's needed. Treat the list below as the definition of "done," reconciling against what already exists rather than starting from scratch.

- **Landing/marketing page** — exists (`(marketing)/page.tsx`). Verify it accurately describes the product.
- **Authentication** (login, register, email verification, logout) — exists as route stubs using Supabase auth-helpers. **Needs the localStorage-vs-Supabase-session duplication resolved first** (see Section 17).
- **Prediction page** — exists (`predict/page.tsx`, `prediction-form.tsx`, `prediction-result.tsx`). Needs to render the full `PredictionResult` shape (Section 7), including SHAP explanations, scoreline distribution, and head-to-head — verify nothing from the API response is being silently dropped.
- **Tournament page** — exists as a route (`tournaments/page.tsx`) but **there's no `lib/api/tournament.ts` client file yet** — this needs building from scratch to call `/tournament/2026/groups`, `/tournament/2026/schedule`, and `/tournament/simulate`. This is likely the single biggest piece of genuinely new frontend work, since the simulation response (48 teams × 8 stage probabilities) needs real UI design (a bracket view, a sortable probability table, or both).
- **Analytics/dashboard pages** — exist (`analytics/page.tsx`, `dashboard/page.tsx`, three chart components). Verify against the actual `/analytics/*` response shapes (Section 7), especially the `is_synthetic` flag on goal-distribution data and the full-dataset-count caveat on total_matches figures.
- **Schedule page** — no dedicated page exists yet distinct from the tournament page; decide whether schedule browsing lives inside the tournament page or gets its own route.
- **Groups page** — same as above; `/tournament/2026/groups` needs a UI home.
- **Rankings** — no dedicated rankings page; likely belongs on the teams list/detail pages (`elo_rating`/`fifa_code`/`wc2026_group` fields are already on `TeamResponse`, just need surfacing — the current `types/index.ts` `Team` interface doesn't include them yet).
- **Matches browsing page** — exists (`matches/page.tsx`, `match-card.tsx`). Needs pagination UI given the (currently unresolved) large `total` count, and must handle null `away_team` gracefully.
- **Teams list + detail pages** — exist (`teams/page.tsx`, `teams/[id]/page.tsx`, `team-card.tsx`).
- **Saved predictions page** — exists (`saved/page.tsx`). Needs the delete flow and accuracy stats wired up.
- **Profile/settings page** — **does not exist yet**, needs building (basic: view profile, sign out, maybe theme toggle given `next-themes` is already a dependency).

---

## 10. UI/UX Goals

The product should feel **modern, premium, and football-themed** — think a polished sports-analytics product, not a generic CRUD admin panel. Specific goals:

- **Apple-level polish**: generous whitespace, considered typography, restrained color use, subtle motion (Framer Motion is already a dependency — use it for page transitions, number count-ups, probability bar fills).
- **Dark mode**: `next-themes` is already installed — implement a real dark mode, not just an afterthought toggle. Football/sports apps often lean dark-by-default.
- **Responsive**: mobile-first is reasonable given how people actually check football predictions (on their phone, often quickly).
- **Minimal, fast**: avoid UI clutter; the data itself (SHAP explanations, Poisson scorelines, tournament probabilities) is already rich — don't bury it in decoration.
- **Loading states**: every API call should have a real loading state (skeletons — `skeleton.tsx` already exists as a primitive — not just spinners) especially for the tournament simulation endpoint, which takes 5–9 seconds.
- **Error states**: every API call can fail (network, 404, 422, 500, 503) — design one consistent error-state pattern and reuse it, don't let failures render blank pages.
- **Accessibility**: Radix UI primitives (already the component foundation) are accessible by default — don't undermine that with custom styling that breaks focus states, contrast, or keyboard navigation.
- **Animations**: purposeful, not decorative — e.g. animating a probability bar filling in, not gratuitous page-load animations.

---

## 11. API Integration Guide

**Existing pattern** (`lib/api/client.ts`): a shared `axios` instance with `NEXT_PUBLIC_API_URL` as the base URL, a request interceptor that attaches a bearer token from `localStorage`, and a response interceptor that redirects to `/auth/login` on a 401. This works but conflicts with the parallel Supabase-session-based auth setup already present (`lib/supabase/*`) — **resolve this before building more on top of it** (see Section 17).

**Recommended practices for new work:**
- **Loading states**: SWR is already a dependency — prefer `useSWR`/`useSWRMutation` over manual `useEffect` + `useState` fetch patterns for GET endpoints, since it gives you loading/error/revalidation for free. The existing `lib/api/*.ts` files are plain async functions (not hooks) — either wrap them in SWR hooks at the call site, or add a thin SWR-hook layer alongside them.
- **Caching**: several backend endpoints are already server-side cached (60s TTL on `/analytics/global`, `/teams/top`) — you don't need to duplicate that caching client-side, but SWR's own revalidation/dedup is still worth using to avoid redundant requests within a session.
- **Error handling**: standardize on parsing `error.response?.data?.detail` (FastAPI's error shape) into whatever your shared error-state component expects.
- **Retry logic**: none currently exists client-side. Worth adding for the tournament simulation endpoint specifically, given it's the slowest and most failure-prone (503 if the model briefly isn't loaded).
- **TypeScript interfaces**: `types/index.ts` exists but is **stale relative to the current API** — it's missing `elo_rating`/`fifa_code`/`wc2026_group`/`ranking_updated_at` on `Team`, doesn't reflect nullable `away_team`/`away_team_id` on `Match`, and has no types at all for the tournament endpoints (`Fifa2026Group`, `Fifa2026Match`, `TournamentSimulationRequest/Response`, `TeamTournamentStats`) or the richer `PredictionResult` fields (`prediction_explanation`, `top_scorelines`, `insights`, `head_to_head`). **Updating this file to match Section 7 exactly should be one of the first things you do.**
- **API client folder structure**: the existing `lib/api/{client,predictions,teams,matches,analytics}.ts` pattern (one file per backend router, each exporting a plain object of async functions) is reasonable and worth continuing — just add `lib/api/tournament.ts` following the same pattern.

---

## 12. Deployment

| Layer | Platform | Production URL | Local URL |
|---|---|---|---|
| Backend | Render | Not yet deployed to a real domain — `render.yaml` is configured but `ALLOWED_ORIGINS` still has a placeholder | `http://localhost:8000` |
| Frontend | Vercel | Not yet deployed | `http://localhost:3000` |
| Database | Supabase | Live project, already provisioned (see `.env` for the real connection details — never hardcode them in code or docs) | Same (Supabase is always "live", no separate local DB) |

To deploy the backend for real: update `render.yaml`'s `ALLOWED_ORIGINS` to the real Vercel domain once known, set the real secret env vars in Render's dashboard (not in the repo), deploy. To deploy the frontend: standard Vercel Next.js deployment, set the 4 env vars from Section 8 in the Vercel dashboard, point `NEXT_PUBLIC_API_URL` at the real deployed backend.

---

## 13. Testing

**Backend:** 80/80 tests passing (`cd backend && pytest -q`). This is frozen — you shouldn't need to touch backend tests unless you find and fix a genuine bug, in which case add a regression test alongside the fix, following the existing patterns in `backend/app/tests/` (fake `AsyncSession`-based mocking for DB-touching endpoints — no live DB access needed to run the suite).

**Frontend testing does not currently exist** — no test runner is configured, no test files exist. Recommend setting this up early: Vitest or Jest + React Testing Library for component tests, Playwright for E2E flows (especially the prediction flow and the tournament simulation flow, given their complexity/latency). This is a real gap worth prioritizing, not an optional nice-to-have, given how data-shape-sensitive this UI necessarily is.

---

## 14. Known Limitations

These are documented, intentional, or simply not-yet-resolved — none of them are secrets, all are discoverable in the repo's `.md` docs, repeated here for convenience:

1. **`GET /matches` and `/analytics/dashboard`/`/analytics/global` are not scoped to the WC-only dataset.** They query/count the full ~49,389-row legacy `matches` table (all competitions, 1872–2026) rather than the 419-row WC-only corpus the ML pipeline uses. This is an open product decision, not a bug: should the public API be WC-only-scoped everywhere, or is browsing all historical matches an intentional broader feature? **A fix for this may have been separately attempted on a branch (`claude/goofy-cray-47bdd4`) that was not merged into `main` as of this handoff — check its state before assuming it's unresolved.** Full writeup: `KNOWN_ASSUMPTIONS.md` item (h).
2. **No rate limiting** is enforced anywhere despite `RATE_LIMIT_PER_MINUTE` existing as a config value — no middleware implements it. Worth adding before real public traffic, especially on the expensive `/tournament/simulate` endpoint.
3. **`ON DELETE CASCADE`** from `teams` → `matches` is a latent data-loss footgun (no team-delete endpoint currently exists, but if one is ever added, it would silently wipe match history).
4. **`GET /matches/analytics/goal-distribution`** is synthetic placeholder data (`is_synthetic: true` on every point) — no goal-minute-level data exists in the database yet.
5. **The draw-prediction calibration** trades precision for recall in a way that's a genuine, still-open design tradeoff (see `MODEL_EVALUATION.md`) — not something the frontend needs to handle differently, just worth knowing predictions may over-call draws somewhat.
6. **No CI/CD pipeline exists** — no automated testing on PRs, no automated deployment.
7. **Small ML training dataset** (419 rows) — model outputs are directionally useful, not laboratory-precise; don't over-promise certainty in the UI copy (e.g. avoid phrasing that implies near-certainty).
8. **The old, broader "seed.sql" dataset** is still present in the repo as an optional/superseded file — not used by anything live, safe to ignore.

**Roadmap items intentionally left for the frontend phase:** all of Section 9's "not yet built" items, a real rankings page, real CI/CD, frontend testing, resolving the dual-auth-mechanism issue, and eventually revisiting limitation #1 above once a product decision is made.

---

## 15. GitHub

- **Repository URL:** `https://github.com/saad-46/FIFA-AI-Score-Prediction-Platform.git`
- **Default branch:** `main`
- **Latest tag / latest stable release:** `backend-v1.0.0` (annotated tag, marks the exact commit the backend was frozen at)
- **Branch strategy:** no formal strategy has been established yet beyond direct commits to `main` so far. **Recommended for frontend work:** create a `frontend` (or per-feature) branch off `main`, open PRs back into `main` rather than committing directly, especially now that the backend is meant to stay frozen — a branch-based workflow makes it much easier to keep backend and frontend changes visibly separate.
- **Recommended workflow:** `git checkout main && git pull && git checkout -b frontend/<feature-name>`, commit frontend work there, open a PR, merge once reviewed. Tag further frontend milestones similarly to `backend-v1.0.0` (e.g. `frontend-v0.1.0` at a first meaningful milestone) if that convention is useful going forward.

---

## 16. Frontend Development Roadmap

### Phase 2: Frontend Development

**Sprint 1 — Foundation & reconciliation**
- Update `types/index.ts` to exactly match the current API contract (Section 7) — this unblocks everything else.
- Resolve the dual auth mechanism (localStorage-JWT-in-axios vs. Supabase-SSR-session) into one coherent pattern.
- Build `lib/api/tournament.ts` (the missing API client).
- Audit every existing page/component against the real API shapes; fix silent mismatches before adding anything new.

**Sprint 2 — Core prediction & teams experience**
- Finish the prediction page: full `PredictionResult` rendering (SHAP explanation UI, scoreline distribution chart, head-to-head display), loading/error states, save-prediction flow.
- Finish teams list/detail: search, top-teams leaderboard, team detail page surfacing Elo/FIFA ranking/group, head-to-head lookup between two teams.

**Sprint 3 — Tournament experience**
- Groups + schedule browsing UI (`/tournament/2026/groups`, `/tournament/2026/schedule`).
- Tournament simulation UI: trigger a simulation, show a loading state appropriate for a 5–9 second wait, render all 48 teams' stage probabilities (bracket visualization and/or sortable table — this is the most visually complex piece of the whole app).

**Sprint 4 — Matches, analytics, dashboard**
- Matches browsing with pagination, filters (team/tournament/year/date range), null-`away_team` handling.
- Analytics/dashboard pages wired to real data, with the synthetic-data and full-dataset-count caveats surfaced honestly in the UI (not hidden).
- Saved predictions page: list, delete, accuracy stats display.

**Sprint 5 — Polish, auth, profile, and hardening**
- Profile/settings page (new).
- Dark mode implementation.
- Full loading/error/skeleton state pass across every page.
- Accessibility pass.
- Frontend testing setup (Vitest/Jest + Playwright) and initial test coverage for the prediction and tournament flows.
- Production deployment: Vercel + Render CORS reconciliation, real env vars in both dashboards.

---

## 17. Claude Instructions

**What NOT to modify:**
- `backend/` — frozen at `backend-v1.0.0`. Bug fixes only, and only if they genuinely block frontend work. Never change ML behavior, never touch the database schema, never add new backend endpoints as a shortcut to solve a frontend problem — if you think you need a new endpoint, that's worth flagging explicitly rather than just adding one.
- `database/` — schema is live and matches the frozen backend exactly.
- The root-level `.md` documentation files — they describe frozen backend state.

**What is already complete:** everything in [Section 4](#4-backend-status). Trust it — it's been validated against live production infrastructure, not just unit-tested in isolation. Don't re-verify backend behavior by reading backend source unless you have a specific reason to suspect a bug.

**Where to focus:** `frontend/` entirely. Start with Section 16's Sprint 1 (type reconciliation + auth cleanup) before building new features — the existing scaffold's staleness will cause confusing bugs if you build on top of it without fixing the foundation first.

**How to maintain code quality:**
- Match the existing code's style (the scaffold already establishes conventions — one API-client file per backend router, Radix-based UI primitives in `components/ui/`, feature-specific components grouped by domain folder).
- Don't add a UI framework/library that duplicates something already installed (e.g. don't add a second charting library alongside Recharts, don't add a second forms library alongside react-hook-form+zod).
- Don't introduce a state-management library (Redux, Zustand, etc.) unless you hit a real, demonstrated need — SWR + React state should cover most of this app's needs.

**Coding standards:** TypeScript strictness should match whatever `tsconfig.json` already specifies — don't loosen it. Prefer explicit types over `any`. Keep API response types in `types/index.ts` as the single source of truth, matching Section 7 exactly (re-derive them from the actual Pydantic schemas in `backend/app/schemas/` if you're ever unsure — those are the ground truth, this document is a snapshot of them).

**Architecture rules:** Keep the existing three-layer frontend structure (`app/` routes → `components/` presentational + feature components → `lib/api/` data layer). Don't fetch data directly inside deeply nested components — fetch at the page/layout level (or via SWR hooks) and pass down, or centralize in a hook per domain.

**Git workflow:** See [Section 15](#15-github) — branch-based work, PRs into `main`, don't commit directly to `main` for anything beyond trivial fixes.

---

## 18. Final Summary

The **FIFA World Cup 2026 AI Prediction Platform** backend is a complete, production-ready FastAPI application: a 134-feature XGBoost prediction engine (regressors + classifier, isotonic-calibrated, SHAP-explainable) with a correctly-wired dynamic Elo system, a Monte Carlo tournament simulator that's aware of the real, in-progress 2026 tournament, and a full REST API (26 endpoints) backed by a live, RLS-secured Supabase Postgres database — all independently validated end-to-end against real production infrastructure this session, with 80/80 tests passing and zero known blocking bugs.

**The backend has been frozen at `backend-v1.0.0` and should be treated as production-ready.** It will not change except for genuine bug fixes discovered during frontend integration.

**The new Claude session's ONLY responsibility is frontend development and frontend/backend integration** — building out the existing Next.js scaffold (which already covers most required pages but was built against a stale API contract) into the polished, modern, football-themed product described in Sections 9–10, reconciling it against the exact API contract in Section 7, and eventually deploying it to Vercel alongside the Render-hosted backend.
