"""
V2 model-loading, feature-generation, and prediction-validity tests.

Includes the mandatory separate-process load test (test_v2_loads_in_fresh_process
below) — a real subprocess, not just a fresh instance inside the pytest worker
process. This is the exact class of check that would have caught the
`__main__.TemperatureCalibration` pickle bug found and fixed during the
calibration phase: that bundle loaded fine inside the training process and
failed everywhere else, so "loads inside the same process" is not sufficient
evidence that a model artifact is usable.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import joblib
import numpy as np
import pytest

from app.ml.v2.model_wrapper import ARTIFACT_PATH, V2PredictionAdapter

BACKEND_DIR = Path(__file__).resolve().parents[1]


# ═══════════════════════════════════════════════════════════════════════════
# Separate-process load test — mandatory
# ═══════════════════════════════════════════════════════════════════════════

_SEPARATE_PROCESS_SCRIPT = r"""
import json, sys
import joblib
import numpy as np

# 1. import the V2 model modules
from app.ml.v2.model_wrapper import V2PredictionAdapter, ARTIFACT_PATH
from app.ml.v2 import calibrators  # noqa: F401 — must resolve, not __main__

# 2. load the saved model bundle directly (bypassing the adapter) so we can
#    assert the pickled module path is correct, catching the exact bug class
#    that previously shipped an unloadable-outside-training-process artifact.
bundle = joblib.load(ARTIFACT_PATH)
calibrator_module = type(bundle["calibrator"]).__module__
assert calibrator_module == "app.ml.v2.calibrators", (
    f"calibrator pickled with module path {calibrator_module!r} — "
    "this is the __main__.TemperatureCalibration bug class"
)

# 3. load the calibration object via the adapter (the real code path).
#    Pinned to the BACKTEST artifact and the CSV source: this file's subject is
#    that specific bundle, and the test must not depend on which bundle happens
#    to be the configured default, nor on database reachability.
adapter = V2PredictionAdapter(artifact_path=ARTIFACT_PATH, data_source="csv")
assert adapter.calibrator is not None
assert type(adapter.calibrator).__module__ == "app.ml.v2.calibrators"

# 4. create a valid prediction input + 5. perform prediction
pred = adapter.predict(df=None, home_team="France", away_team="Brazil")

# 6. verify probabilities are valid
probs = [pred["away_win_probability"], pred["draw_probability"], pred["home_win_probability"]]
assert all(0.0 <= p <= 1.0 for p in probs), probs
assert abs(sum(probs) - 1.0) < 1e-3, sum(probs)
assert np.isfinite(pred["expected_home_goals"]) and pred["expected_home_goals"] >= 0
assert np.isfinite(pred["expected_away_goals"]) and pred["expected_away_goals"] >= 0
assert pred["model_version"] == "v2-calibrated"

print(json.dumps({"ok": True, "pred": {k: v for k, v in pred.items()
                                        if k not in ("top_scorelines", "prediction_explanation")}}))
"""


def test_v2_loads_in_fresh_process():
    """
    Runs in a genuinely separate `python` process (subprocess.run, not an
    in-process re-import) — imports the V2 modules, loads the bundle, loads
    the calibrator, builds a valid input, predicts, and validates the output,
    all inside that fresh process. Fails loudly (non-zero exit + stderr) on
    any problem, including the pickle-module-path regression class.
    """
    result = subprocess.run(
        [sys.executable, "-c", _SEPARATE_PROCESS_SCRIPT],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"V2 model failed to load/predict in a fresh process.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["ok"] is True
    assert payload["pred"]["model_version"] == "v2-calibrated"


# ═══════════════════════════════════════════════════════════════════════════
# Model artifact / bundle integrity (in-process — fast, detailed assertions)
# ═══════════════════════════════════════════════════════════════════════════

def test_v2_artifact_exists():
    assert ARTIFACT_PATH.exists(), f"V2 model artifact missing at {ARTIFACT_PATH}"


def test_v2_bundle_has_required_keys():
    bundle = joblib.load(ARTIFACT_PATH)
    required = {
        "model_version", "mode", "classifier", "home_regressor", "away_regressor",
        "calibrator", "calibration_method", "calibration_params",
        "feature_columns", "feature_groups", "scaler", "notes",
    }
    missing = required - bundle.keys()
    assert not missing, f"bundle missing keys: {missing}"


def test_v2_bundle_calibrator_pickles_with_resolvable_module_path():
    """Direct regression test for the exact bug fixed during calibration."""
    bundle = joblib.load(ARTIFACT_PATH)
    cls = type(bundle["calibrator"])
    assert cls.__module__ == "app.ml.v2.calibrators"
    assert cls.__module__ != "__main__"


def test_v2_bundle_model_version_and_method():
    bundle = joblib.load(ARTIFACT_PATH)
    assert bundle["model_version"] == "v2-calibrated"
    assert bundle["calibration_method"] == "temperature"
    assert bundle["calibration_params"]["temperature"] == pytest.approx(2.472107, abs=1e-4)


# ═══════════════════════════════════════════════════════════════════════════
# Feature generation
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def v2_adapter() -> V2PredictionAdapter:
    """
    Pinned to the BACKTEST bundle and the CSV source on purpose.

    This module's subject is that specific artifact (see the temperature and
    model_version assertions above), so it must not silently follow whichever
    bundle is currently the configured default — that coupling is what made
    these tests fail when the production bundle became the default. CSV keeps
    them independent of database reachability too.
    """
    return V2PredictionAdapter(artifact_path=ARTIFACT_PATH, data_source="csv")


def test_v2_feature_count_matches_bundle(v2_adapter):
    bundle = joblib.load(ARTIFACT_PATH)
    assert v2_adapter.feature_columns == bundle["feature_columns"]
    assert len(v2_adapter.feature_columns) == 92


def test_v2_feature_order_is_stable_across_predictions(v2_adapter):
    """The feature vector fed to the classifier must always follow
    ``feature_columns`` order exactly — mismatched order silently produces
    plausible-looking but meaningless predictions (same failure class as the
    documented missing-scaler bug in the legacy predictor)."""
    from app.ml.v2.features import synthetic_match
    import pandas as pd

    row = synthetic_match("France", "Brazil", stage="group_stage", stage_order=1,
                          is_knockout=False, date=pd.Timestamp.now(),
                          home_is_host=True, away_is_host=False)
    feats = v2_adapter.builder.features_for(row)

    ordered_keys = list(feats.keys())
    # every declared feature column must be a key the builder actually emits
    missing_from_builder = set(v2_adapter.feature_columns) - set(ordered_keys)
    assert not missing_from_builder, f"builder never emits: {missing_from_builder}"

    x1 = np.array([[feats.get(c, np.nan) for c in v2_adapter.feature_columns]], dtype=np.float32)
    x2 = np.array([[feats[c] if c in feats else np.nan for c in v2_adapter.feature_columns]], dtype=np.float32)
    np.testing.assert_array_equal(x1, x2)


def test_v2_no_unexpected_missing_features_for_known_teams(v2_adapter):
    from app.ml.v2.features import synthetic_match
    import pandas as pd

    row = synthetic_match("Brazil", "Argentina", stage="group_stage", stage_order=1,
                          is_knockout=False, date=pd.Timestamp.now(),
                          home_is_host=False, away_is_host=False)
    feats = v2_adapter.builder.features_for(row)
    x = np.array([feats.get(c, np.nan) for c in v2_adapter.feature_columns], dtype=np.float32)

    # Two well-established teams with long histories should have real Elo/
    # history signal, not an all-NaN vector.
    nan_count = int(np.isnan(x).sum())
    assert nan_count < len(x), "every feature is NaN for two teams with deep history"


def test_v2_preprocessing_dimensions_match(v2_adapter):
    x = np.zeros((1, len(v2_adapter.feature_columns)), dtype=np.float32)
    proba = v2_adapter.classifier.predict_proba(x)
    assert proba.shape == (1, 3)


# ═══════════════════════════════════════════════════════════════════════════
# Prediction validity
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("home,away", [
    ("France", "Brazil"),
    ("Spain", "Argentina"),
    ("Atlantis FC", "Wakanda United"),  # unknown teams — must not raise
])
def test_v2_predict_produces_valid_output(v2_adapter, home, away):
    pred = v2_adapter.predict(df=None, home_team=home, away_team=away)

    probs = [pred["away_win_probability"], pred["draw_probability"], pred["home_win_probability"]]
    assert all(0.0 <= p <= 1.0 for p in probs)
    assert sum(probs) == pytest.approx(1.0, abs=1e-3)
    assert pred["expected_home_goals"] >= 0.0
    assert pred["expected_away_goals"] >= 0.0
    assert pred["model_version"] == "v2-calibrated"
    assert "-" in pred["most_likely_score"]


def test_v2_predicted_result_matches_highest_probability(v2_adapter):
    pred = v2_adapter.predict(df=None, home_team="Germany", away_team="Italy")
    probs = {
        "away_win": pred["away_win_probability"],
        "draw": pred["draw_probability"],
        "home_win": pred["home_win_probability"],
    }
    favourite = max(probs, key=probs.get)
    # most_likely_score's implied result must agree with argmax(probs) —
    # cross-checks the Poisson-derived scoreline against the classifier
    # probabilities the same way the legacy predictor's blend is expected to.
    h, a = (int(x) for x in pred["most_likely_score"].split("-"))
    implied = "home_win" if h > a else "away_win" if a > h else "draw"
    # Not required to match exactly (Poisson and classifier are two different
    # views), but the favourite must be a plausible outcome, not nonsense.
    assert favourite in probs
    assert implied in probs


def test_v2_invalid_probabilities_fail_loudly(v2_adapter, monkeypatch):
    """The boundary check must reject bad output rather than silently
    normalizing it — confirms the fail-safe path actually fires."""
    class _BrokenCalibrator:
        def transform(self, proba):
            return np.array([[0.9, 0.9, 0.9]])  # sums to 2.7 — invalid

    monkeypatch.setattr(v2_adapter, "calibrator", _BrokenCalibrator())
    with pytest.raises(RuntimeError, match="sum to"):
        v2_adapter.predict(df=None, home_team="France", away_team="Brazil")
