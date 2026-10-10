# ML pipeline V3 — how it works, how to reproduce it, how to roll it back

Pipeline version `3.0.0` · feature schema `v3-features-1` · written 2026-10-10

The audit that led to this pipeline, its benchmark and its limitations are in
[ML_AUDIT_2026-10-10.md](ML_AUDIT_2026-10-10.md). This file is the operating manual.

## What it is

```
committed match corpus (49,945 internationals, 1872 → 2026-10-06)
        │  app/ml/v3/data.py        validate, normalise names, tier each competition
        ▼
chronological rating walk            app/ml/v3/ratings.py
  snapshot (state BEFORE the match) → advance (apply the result)
  Elo · online attack/defence · form · rest · head-to-head
        │  app/ml/v3/features.py    14 registered pre-match features
        ▼
Poisson / Dixon–Coles  +  XGBoost    app/ml/v3/models.py
        │  equal-weight blend → temperature scaling      app/ml/v3/pipeline.py
        ▼
win / draw / loss, expected goals, scoreline matrix, shoot-out probability
        │
        ├─ single fixture      app/ml/v3/inference.py  → POST /predictions/predict
        └─ tournament          app/ml/v3/tournament_fast.py (vectorised)
                               app/ml/v3/tournament.py (readable reference + rules)
                               → POST /tournament/simulate
```

Training never runs inside the API. The API loads a bundle, checks it against its
manifest, and rebuilds team state by running the *same* rating walk over the
*same* corpus. There is no second feature implementation for serving to drift from.

## Data

| | |
|---|---|
| Source | `martj42/international_results` (CC0), commit `b7a3a8ee5d37780c6a03101c188658fd439e241d` |
| Files | `backend/app/data/raw/international_results/{results,shootouts,former_names}.csv`, stored byte-for-byte; hashes in `SOURCE.json` |
| Fingerprint | `b38434f8f74cd9fa` (first 16 hex of the SHA-256 of `results.csv`), recorded in every manifest |
| Score definition | after extra time, shoot-outs excluded (a shoot-out is a draw plus a recorded winner) |
| Bracket data | `backend/app/data/canonical/wc2026_third_place_allocation.json` — FIFA Annex C, 495 combinations |

Seven team names are mapped to the application's registry names (`United States`→`USA`,
`Czech Republic`→`Czechia`, `Turkey`→`Türkiye`, `Iran`→`IR Iran`, `Ivory Coast`→`Côte d'Ivoire`,
`DR Congo`→`Congo DR`, `Cape Verde`→`Cabo Verde`). Nothing else is altered; rows that break a
hard rule are dropped and counted in `data_validation_report.json` (none were, in this snapshot).

## Reproduce

From `backend/`, with the project virtualenv:

```bash
python -m app.ml.v3.train all
```

That runs, in order: `validate` → `tune` (rating parameters, development folds only) →
`benchmark` (all candidates, selection, then the untouched 2026 test) → `fit` (two bundles
and manifests) → `forecast` (50,000-simulation pre-tournament forecast). Each step can be
run alone. Seeds are fixed (`42` for models, `20260611` for simulation).

```bash
python -m app.ml.v3.compare_incumbent
```

scores V3 against the two existing models on the 104 World Cup 2026 matches.

Everything lands in `backend/app/ml/v3/artifacts/`:

| File | Content |
|---|---|
| `model_wc2026_pretournament.joblib` + `manifest_…json` | nothing fitted on or after 2026-06-11 |
| `model_current.joblib` + `manifest_…json` | trained through the last match in the corpus |
| `ACTIVE.json` | which bundle `/predictions/predict` serves, and the previous one |
| `benchmark_report.json`, `BENCHMARK_V3.md` | every candidate on every fold |
| `rating_search.json` | every rating configuration tried |
| `data_validation_report.json` | data contract results and the feature registry |
| `wc2026_pretournament_forecast.json` | the pre-tournament forecast |
| `incumbent_comparison.json` | V3 against v1.0.0 and the v2.1.0 ledger |

A manifest records: pipeline and schema version, feature list, information cutoff, corpus
fingerprint and source commit, rating configuration, model parameters, training window and
row counts, library versions, and the SHA-256 of the bundle.

## Serving

`PREDICTION_ENGINE` chooses the engine for both endpoints. The default is `legacy`; V3 is an
explicit opt-in: set `PREDICTION_ENGINE=v3` and restart. Any other value means `legacy`.
Everything below describes the V3 engine.

On load the service refuses to start a bundle — and the API answers **503, with no numbers** —
if any of these fail: bundle checksum, feature schema, feature list, corpus fingerprint,
shoot-out file hash. A team with no recorded matches is a **422**, not a default prediction.

`POST /predictions/predict` — unchanged request and response. `home_team` is team A;
`neutral_venue=true` removes home advantage, and the result is then independent of the order
the teams are given in. `confidence_score` keeps its old meaning (how much match history backs
the less-documented side); the probability of the predicted outcome is
`prediction_explanation.confidence`.

`POST /tournament/simulate` — unchanged request; the response gains an optional `meta` block,
and the request an optional `seed`.

| Request | `meta.mode` | What it is |
|---|---|---|
| `use_fifa_2026_groups=true, use_real_results=false` | `pre_tournament` | all 104 matches simulated from matches before 2026-06-11 |
| `use_fifa_2026_groups=true, use_real_results=true` | `after_group_stage` | real group results fixed, ratings as of 2026-06-28, knockout rounds simulated |
| custom `groups` | `custom_groups` | 12 groups of real national teams, neutral venues, latest ratings |

The 2026 World Cup is over. No mode predicts the future and no mode is fed a knockout result;
the real bracket is served by `/tournament/2026/bracket`.

**Only under V3:** custom groups must name teams the corpus knows (FIFA code or name);
placeholder names get 422. The legacy engine still accepts them, as before.

Changes that apply to the legacy engine too: its simulator now asks the predictor about team
names instead of FIFA codes (the USA fix); `/tournament/simulate` responses carry `meta`
(`engine: "legacy"`); and the "strong at home" insight no longer counts neutral-ground matches.

Measured latency on the development machine (one process): single prediction ~65 ms after a
~1.3 s first load; 10,000 simulations ~1.5 s (+~1.5 s the first time a mode is requested);
100,000 simulations ~11.6 s. Identical official requests are served from a small in-memory cache.

## Rollback

| Situation | Action |
|---|---|
| Leave V3 | remove `PREDICTION_ENGINE` (or set it to `legacy`) and restart. That is also the state of a fresh deployment: V3 is never served unless asked for. The v1.0.0 model and the V2 flag (`USE_V2_MODEL`) are untouched. |
| Return to the previous V3 bundle | `python -m app.ml.v3.train rollback` swaps `active` and `previous` in `ACTIVE.json`. (There is no previous V3 bundle yet — this is the first.) |
| A bundle fails validation in production | nothing to do to stay safe: the API already answers 503 rather than guessing. Fix the artefact or roll back as above. |

No legacy artefact, dataset or database record was deleted or modified.

## Refreshing the data

1. Replace the three CSVs with a newer upstream snapshot.
2. Update `SOURCE.json` (commit, date, row counts, hashes).
3. `python -m app.ml.v3.train all` — the fingerprint changes, so old bundles stop loading until refitted. That is intended.
4. Run the tests. Review `BENCHMARK_V3.md` before deploying.

The `wc2026_pretournament` bundle must keep its 2026-06-11 cutoff. Later matches may sit in
the corpus; the bundle and its team state never read them.

## Tests

`backend/tests/test_v3_pipeline.py` (41), `test_v3_tournament.py` (20), `test_v3_api.py` (33),
and `test_simulator_team_identity.py` (5, legacy simulator).

```bash
python -m pytest tests/test_v3_pipeline.py tests/test_v3_tournament.py tests/test_v3_api.py tests/test_simulator_team_identity.py -q
```

## Known limits

Stated plainly in section 9 of the audit: no player, injury, squad-value or lineup data;
ties that FIFA settles by fair-play points or ranking are settled by lot; the model never
makes a draw its single most likely outcome; extra-time scoring is an assumption (one third of
the 90-minute rate), not a fitted quantity.
