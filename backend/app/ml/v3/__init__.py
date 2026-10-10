"""
V3 match-forecasting pipeline.

One chronological pass over men's senior international results produces every
pre-match feature; the same code path builds training rows and serves live
predictions, so there is no second implementation to drift.

    data.py        data contract, validation, team identity
    ratings.py     chronological Elo + attack/defence state (the feature source)
    features.py    feature registry and the shared feature builder
    models.py      baselines, Elo-ordered-logit, Poisson/Dixon-Coles, MLR, XGBoost
    calibration.py temperature scaling
    backtest.py    walk-forward evaluation and metrics
    tournament.py  rules-driven Monte Carlo tournament engine
    train.py       reproducible training / selection / manifest
    inference.py   artifact loading + prediction service used by the API

Nothing here imports from app.ml.models or app.ml.v2: the legacy predictor and
the V2 bundle stay loadable unchanged, which is the rollback path.
"""

PIPELINE_VERSION = "3.0.0"
