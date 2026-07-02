# FIFA AI Score Prediction Platform

An AI-powered platform for predicting FIFA match outcomes and simulating the FIFA World Cup 2026 tournament. A FastAPI backend serves XGBoost-based predictions (expected goals, win/draw/loss probabilities, SHAP explanations) and a Monte Carlo tournament simulator built on the official 48-team, 12-group FIFA World Cup 2026 format; a Next.js frontend consumes the API for match prediction, team analytics, and tournament visualization.

## Main Features

- AI Match Prediction (home/away expected goals via XGBoost)
- Win / Draw / Loss Probabilities (Poisson score-matrix derived)
- Poisson Score Simulation with calibrated probabilities
- FIFA World Cup 2026 Tournament Simulator (48 teams, 12 groups, Monte Carlo Round of 32 → Final)
- SHAP Explainability for every prediction
- FastAPI REST backend with async SQLAlchemy
- Supabase (PostgreSQL) database with Row Level Security
- Next.js 15 frontend (TypeScript, App Router)

## Tech Stack

**Backend:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Uvicorn
**Database:** PostgreSQL via Supabase
**ML:** XGBoost, scikit-learn, Pandas, NumPy, SHAP, Optuna
**Frontend:** Next.js 15, TypeScript, Tailwind CSS

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

Provision the database (run in the Supabase SQL editor, in order):
```
database/schema.sql
database/seed_fifa_2026_teams.sql   # real FIFA World Cup 2026 teams (48 teams, name + country)
database/seed.sql                    # optional: historical match data
```

### Frontend setup

```bash
cd frontend
npm install
cp .env.local.example .env.local
```

### Run server

```bash
# Backend (from backend/)
uvicorn app.main:app --reload --port 8000
# API docs at http://localhost:8000/docs

# Frontend (from frontend/)
npm run dev
# App at http://localhost:3000
```

### Run tests

```bash
cd backend
pytest -q
```

## Project Structure

```
fifa-score-predictor/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/   # predictions, matches, teams, analytics, tournament
│   │   ├── core/                # config, security, in-process cache
│   │   ├── data/fifa_2026/      # official 2026 groups/schedule/venues
│   │   ├── db/                  # SQLAlchemy engine/session
│   │   ├── ml/                  # training, feature engineering, tournament simulator
│   │   ├── models/              # SQLAlchemy ORM models
│   │   ├── schemas/             # Pydantic v2 request/response models
│   │   └── services/            # business logic layer
│   └── tests/
├── frontend/                    # Next.js 15 app
└── database/                    # schema + seed SQL
```

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for a detailed system overview, [`API_DOCUMENTATION.md`](API_DOCUMENTATION.md) for the full endpoint reference, [`MODEL_PIPELINE.md`](MODEL_PIPELINE.md) for the ML pipeline, [`TOURNAMENT_ENGINE.md`](TOURNAMENT_ENGINE.md) for the simulation engine, and [`KNOWN_ASSUMPTIONS.md`](KNOWN_ASSUMPTIONS.md) for documented data-provenance assumptions.

## Future Improvements

- Populate Elo ratings at inference time (currently computed only during offline training)
- Add rate limiting to public endpoints, especially tournament simulation
- Real by-minute goal-distribution analytics (currently a documented synthetic placeholder)
- Expand automated test coverage for teams/matches/analytics endpoints
