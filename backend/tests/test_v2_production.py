"""
Production-readiness tests: production model artifact, Supabase data source,
SHAP explanations, and feature-flag edge cases.

Covers Phases 6, 10 and 11 of the production-readiness plan.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import joblib
import numpy as np
import pytest

from app.ml.v2.model_wrapper import (
    ARTIFACT_PATH, PRODUCTION_ARTIFACT_PATH, V2PredictionAdapter,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.filterwarnings("ignore")


# ═══════════════════════════════════════════════════════════════════════════
# Phase 10 — production artifact loads from a genuinely fresh process
# ═══════════════════════════════════════════════════════════════════════════

_PRODUCTION_SUBPROCESS = r"""
import json
import joblib
import numpy as np

from app.ml.v2.model_wrapper import V2PredictionAdapter, PRODUCTION_ARTIFACT_PATH
from app.ml.v2 import calibrators  # noqa: F401

bundle = joblib.load(PRODUCTION_ARTIFACT_PATH)
assert bundle["model_version"] == "v2-production-calibrated", bundle["model_version"]
assert bundle["mode"] == "CURRENT_PRODUCTION", bundle["mode"]

# calibrator must pickle with a resolvable path, not __main__
mod = type(bundle["calibrator"]).__module__
assert mod == "app.ml.v2.calibrators", f"calibrator module is {mod!r}"

# feature configuration present and coherent
assert isinstance(bundle["feature_columns"], list)
assert len(bundle["feature_columns"]) == 92, len(bundle["feature_columns"])
assert bundle["scaler"] is None  # documented: no scaling needed for tree models

# full prediction path through the adapter, reading from CSV so this test does
# not depend on database reachability
adapter = V2PredictionAdapter(artifact_path=PRODUCTION_ARTIFACT_PATH, data_source="csv")
pred = adapter.predict(df=None, home_team="France", away_team="Brazil")

probs = [pred["away_win_probability"], pred["draw_probability"], pred["home_win_probability"]]
assert all(0.0 <= p <= 1.0 for p in probs), probs
assert abs(sum(probs) - 1.0) < 1e-3, sum(probs)
assert pred["expected_home_goals"] >= 0 and np.isfinite(pred["expected_home_goals"])
assert pred["model_version"] == "v2-production-calibrated"

print(json.dumps({"ok": True, "version": pred["model_version"], "probs": probs}))
"""


def test_production_model_loads_in_fresh_process():
    """Same mandatory subprocess check as the backtest bundle, for the
    artifact that would actually serve production traffic."""
    result = subprocess.run(
        [sys.executable, "-c", _PRODUCTION_SUBPROCESS],
        cwd=str(BACKEND_DIR), capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, (
        f"production model failed in a fresh process.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["ok"] is True
    assert payload["version"] == "v2-production-calibrated"


def test_production_artifact_exists():
    assert PRODUCTION_ARTIFACT_PATH.exists()


def test_backtest_artifact_still_exists_and_is_distinct():
    """The two artifacts must remain separate files with separate versions —
    the backtest bundle is the only source of quotable WC2026 accuracy."""
    assert ARTIFACT_PATH.exists()
    assert ARTIFACT_PATH != PRODUCTION_ARTIFACT_PATH
    backtest = joblib.load(ARTIFACT_PATH)
    production = joblib.load(PRODUCTION_ARTIFACT_PATH)
    assert backtest["model_version"] == "v2-calibrated"
    assert production["model_version"] == "v2-production-calibrated"
    assert backtest["mode"] == "WC2026_BACKTEST"
    assert production["mode"] == "CURRENT_PRODUCTION"


def test_backtest_calibration_unchanged():
    """T = 2.472 on the backtest artifact is a fixed, approved value."""
    backtest = joblib.load(ARTIFACT_PATH)
    assert backtest["calibration_method"] == "temperature"
    assert backtest["calibration_params"]["temperature"] == pytest.approx(2.472107, abs=1e-5)


# ═══════════════════════════════════════════════════════════════════════════
# Phase 6 — SHAP
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def adapter() -> V2PredictionAdapter:
    # CSV source keeps SHAP tests independent of database availability.
    return V2PredictionAdapter(artifact_path=PRODUCTION_ARTIFACT_PATH, data_source="csv")


def test_shap_explainer_loads(adapter):
    assert adapter.explainer is not None
    assert adapter.explainer.is_ready, "SHAP TreeExplainer failed to initialise"


def test_shap_feature_names_match_model(adapter):
    assert adapter.explainer.feature_columns == adapter.feature_columns
    assert len(adapter.explainer.feature_columns) == 92


def test_shap_input_dimensions_match_prediction_input(adapter):
    """SHAP must be fed the exact vector the model scored — a dimension
    mismatch here is the silent-wrong-explanation failure mode."""
    from app.ml.v2.features import synthetic_match
    import pandas as pd

    row = synthetic_match("France", "Brazil", stage="group_stage", stage_order=1,
                          is_knockout=False, date=pd.Timestamp.now(),
                          home_is_host=True, away_is_host=False)
    feats = adapter.builder.features_for(row)
    x = np.array([[feats.get(c, np.nan) for c in adapter.feature_columns]], dtype=np.float32)
    assert x.shape == (1, 92)

    explanation = adapter.explainer.explain(x, "home_win")
    assert explanation is not None
    assert explanation["n_features"] == 92


def test_shap_explanation_is_generated_and_structured(adapter):
    pred = adapter.predict(df=None, home_team="France", away_team="Brazil", explain=True)
    exp = pred["prediction_explanation"]
    assert exp, "explanation should be present when SHAP is ready"
    assert exp["predicted_outcome"] in ("home_win", "draw", "away_win")
    assert 0.0 <= exp["confidence"] <= 1.0
    for bucket in ("top_positive_features", "top_negative_features"):
        for item in exp[bucket]:
            assert set(item) == {"feature", "readable_name", "impact"}
            assert item["feature"] in adapter.feature_columns
            assert isinstance(item["impact"], float)


def test_shap_explains_the_predicted_class(adapter):
    """The explanation must describe the class the model actually predicted,
    not a fixed class — attributing the wrong class is worse than none."""
    pred = adapter.predict(df=None, home_team="Brazil", away_team="Argentina", explain=True)
    probs = {
        "away_win": pred["away_win_probability"],
        "draw": pred["draw_probability"],
        "home_win": pred["home_win_probability"],
    }
    assert pred["prediction_explanation"]["predicted_outcome"] == max(probs, key=probs.get)


def test_shap_positive_and_negative_are_signed_correctly(adapter):
    pred = adapter.predict(df=None, home_team="Spain", away_team="Germany", explain=True)
    exp = pred["prediction_explanation"]
    assert all(f["impact"] > 0 for f in exp["top_positive_features"])
    assert all(f["impact"] < 0 for f in exp["top_negative_features"])


def test_shap_can_be_skipped(adapter):
    """Explanations must be omissible so a latency-sensitive caller can skip
    the SHAP cost."""
    pred = adapter.predict(df=None, home_team="France", away_team="Brazil", explain=False)
    assert pred["prediction_explanation"] == {}


def test_goal_explanations_are_separate_from_result(adapter):
    """xG attributions live in a different space and must not be merged into
    the result explanation."""
    from app.ml.v2.features import synthetic_match
    import pandas as pd

    row = synthetic_match("France", "Brazil", stage="group_stage", stage_order=1,
                          is_knockout=False, date=pd.Timestamp.now())
    feats = adapter.builder.features_for(row)
    x = np.array([[feats.get(c, np.nan) for c in adapter.feature_columns]], dtype=np.float32)
    goals = adapter.explainer.explain_goals(x)
    assert goals is not None
    assert "home_expected_goals" in goals and "away_expected_goals" in goals
    assert "log expected goals" in goals["space"]


# ═══════════════════════════════════════════════════════════════════════════
# Phase 11 — feature-flag edge cases
# ═══════════════════════════════════════════════════════════════════════════

def test_missing_artifact_fails_loudly_not_silently(tmp_path):
    """A missing V2 artifact must raise a clear error, NOT silently fall back
    to legacy — silent fallback would mean serving a different model than the
    operator asked for, with no signal."""
    missing = tmp_path / "does_not_exist.pkl"
    with pytest.raises(FileNotFoundError, match="V2 model artifact not found"):
        V2PredictionAdapter(artifact_path=missing, data_source="csv")


def test_missing_artifact_error_mentions_how_to_recover(tmp_path):
    missing = tmp_path / "nope.pkl"
    try:
        V2PredictionAdapter(artifact_path=missing, data_source="csv")
    except FileNotFoundError as exc:
        message = str(exc)
        assert "USE_V2_MODEL=false" in message
        assert "calibrate" in message
    else:
        pytest.fail("expected FileNotFoundError")


def test_invalid_data_source_rejected():
    from app.ml.v2.data_source import load_canonical_from
    with pytest.raises(ValueError, match="unknown V2 data source"):
        load_canonical_from("mysql")  # type: ignore[arg-type]
