"""
FIFA AI — Prediction Explainability
===================================

Provides SHAP-based feature attributions for match predictions.
Explains the XGBoost Classifier's decision by computing SHAP values
for the predicted class.

Usage
-----
    from app.ml.explainability import PredictionExplainer
    
    explainer = PredictionExplainer(predictor.result_model, predictor.feature_columns)
    explanation = explainer.explain(X_s, predicted_class_idx)
"""

from __future__ import annotations

import logging
import warnings
from typing import Dict, List, Any

import numpy as np
import xgboost as xgb

try:
    # shap's plotting submodule (shap.plots.colors._colorconv) emits a large
    # number of numpy DeprecationWarnings on import that are purely internal
    # to the upstream package and unrelated to the TreeExplainer API used
    # here. Suppress them locally so they don't drown out real warnings.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        import shap
except ImportError:
    shap = None

logger = logging.getLogger(__name__)


def _format_feature_name(name: str) -> str:
    """Format raw feature names into human-readable strings."""
    # E.g. 'home_momentum_20' -> 'Home Momentum (20)'
    # 'elo_difference' -> 'Elo Rating Difference'
    parts = name.split('_')

    if name in ('elo_difference', 'elo_diff'):
        return 'Elo Rating Difference'
    
    # Handle team prefix
    prefix = ""
    if parts[0] in ['home', 'away']:
        prefix = f"{parts[0].capitalize()} Team's "
        parts = parts[1:]
        
    # Handle window suffix
    suffix = ""
    if parts[-1].isdigit():
        suffix = f" (Past {parts[-1]} Matches)"
        parts = parts[:-1]
        
    core_feature = " ".join(p.capitalize() for p in parts)
    
    return f"{prefix}{core_feature}{suffix}".strip()


class PredictionExplainer:
    def __init__(self, model: xgb.XGBClassifier, feature_columns: List[str]):
        """
        Initialize the explainer with a trained XGBClassifier and feature names.
        """
        self.model = model
        self.feature_columns = feature_columns
        self.explainer = None
        self._is_ready = False
        
        if shap is None:
            logger.warning("SHAP is not installed. Explanations will not be generated.")
            return
            
        try:
            # TreeExplainer is extremely fast for XGBoost
            self.explainer = shap.TreeExplainer(self.model)
            self._is_ready = True
        except Exception as e:
            logger.error(f"Failed to initialize SHAP TreeExplainer: {e}")

    def is_ready(self) -> bool:
        return self._is_ready

    def explain(self, X_s: np.ndarray, predicted_class_idx: int, predicted_outcome: str, confidence: float) -> Dict[str, Any]:
        """
        Generate an explanation for a single prediction.
        
        Parameters
        ----------
        X_s : np.ndarray
            Scaled feature vector of shape (1, n_features).
        predicted_class_idx : int
            The predicted class index (0: Away Win, 1: Draw, 2: Home Win) to explain.
        predicted_outcome : str
            The predicted outcome string (e.g., "Home Win").
        confidence : float
            The model's confidence in the prediction.
            
        Returns
        -------
        Dict containing predicted_outcome, confidence, and top positive/negative factors.
        """
        if not self.is_ready():
            return {
                "predicted_outcome": predicted_outcome,
                "confidence": confidence,
                "top_positive_features": [],
                "top_negative_features": []
            }
            
        if X_s.shape[0] != 1:
            logger.warning("Explainer expects a single sample (shape 1, n_features).")
            X_s = X_s[0:1]

        try:
            # Get SHAP values. For multi-class XGBoost, shape is (1, n_features, n_classes)
            # or a list of length n_classes with arrays of shape (1, n_features).
            shap_values = self.explainer.shap_values(X_s)
            
            # Extract values for the predicted class
            if isinstance(shap_values, list):
                # Older SHAP versions
                class_shap = shap_values[predicted_class_idx][0]
            elif len(shap_values.shape) == 3:
                # Newer SHAP versions: (n_samples, n_features, n_classes)
                class_shap = shap_values[0, :, predicted_class_idx]
            else:
                # Binary classification fallback (shouldn't happen here, but safe to handle)
                class_shap = shap_values[0]
                
            # Pair features with their SHAP values
            feature_effects = []
            for i, feature_name in enumerate(self.feature_columns):
                val = float(class_shap[i])
                feature_effects.append({
                    "feature": feature_name,
                    "readable_name": _format_feature_name(feature_name),
                    "impact": val
                })
                
            # Sort by absolute impact to find top drivers
            feature_effects.sort(key=lambda x: abs(x["impact"]), reverse=True)
            
            # Separate into positive (pushing towards the prediction) 
            # and negative (pushing away from the prediction)
            positives = [f for f in feature_effects if f["impact"] > 0]
            negatives = [f for f in feature_effects if f["impact"] < 0]
            
            # Sort negatives so the most negative (highest absolute value) is first
            negatives.sort(key=lambda x: x["impact"])
            
            return {
                "predicted_outcome": predicted_outcome,
                "confidence": confidence,
                "top_positive_features": positives[:5],
                "top_negative_features": negatives[:5],
            }
            
        except Exception as e:
            logger.error(f"Failed to generate explanation: {e}")
            return {
                "predicted_outcome": predicted_outcome,
                "confidence": confidence,
                "top_positive_features": [],
                "top_negative_features": []
            }
