# Model Evaluation Report — FIFA World Cup 2026 Retrain

Generated 2026-07-03, updated 2026-07-04 after the empirical feature-pruning
pass (see "Empirical feature pruning" section below — this is the pass
flagged as an open gap in the original 2026-07-03 report; that section is
now closed). Covers the model retrained by the ML Engineering wave on the
new WC-only corpus (`backend/app/data/processed/matches_historical.csv`, 419 rows: 330 real matches 2002–2022 + 89 real in-progress-2026 matches; 13 not-yet-played rows excluded from training, leaving 406 completed matches, of which 376 were used for the final fit after the last CV fold's holdout).

**Caveat this report leads with, not buries**: this is a genuinely small dataset for a 134-feature XGBoost model (163 before this pass's pruning). A 134-feature-to-376-sample ratio is still high-dimensional relative to sample size, and standard errors on every metric below are wide. Treat these as directionally informative, not precise.

## Training configuration
- **Samples**: 376 training (after CV), **134 features** (post-pruning; was 163 — see "Empirical feature pruning" below), `count:poisson` objective for the goal regressors, `multi:softprob` for the outcome classifier.
- **Split strategy: expanding-window walk-forward CV by tournament year**, not a single 70/30 or 80/20 split. Justification: football team strength drifts over multi-year windows, so a random shuffle split would leak future-team-form information into training in a way real deployment never has access to; a single chronological hold-out (e.g. last 20%) would leave a test set of well under 100 rows given the WC-only corpus size, too small to trust one point estimate. Walk-forward by WC edition (train on all prior editions, validate on the next one) uses every edition as a validation fold exactly once while never training on future data relative to that fold, and reports a mean ± std across 6 folds instead of one noisy number.
- **Calibration**: isotonic regression selected over Platt scaling and raw probabilities based on mean Brier score across the three outcome classes (isotonic 0.2008 vs Platt 0.2120 vs raw 0.2224 — isotonic wins on Brier despite a higher ECE than Platt's near-zero 0.00004, because Platt's near-zero ECE come from being under-confident nearly everywhere on a tiny calibration set, not from genuinely better-calibrated probabilities — isotonic's ECE of 0.051 is still good in absolute terms).
- **Draw handling**: football draw prediction is a known hard problem (draws are a real, frequent, low-signal outcome). A `draw_boost` of 1.05 was tuned to trade raw accuracy for draw recall: raw draw recall 0.18 / raw accuracy 0.368 vs draw-boosted recall 1.0 / accuracy 0.289. **Read this trade-off carefully**: a draw recall of 1.0 at 0.222 precision means the boosted classifier is likely over-predicting draws broadly, not cleanly detecting them — this is a real design trade-off (catch more real draws vs. more false-positive draw calls) and not an unambiguous improvement. Worth revisiting with more data before treating the boosted setting as final.

## Cross-validation results (6 folds, expanding window by WC edition) — POST-PRUNING (134 features, current production model)

| Fold | Train editions | Val edition | n_train | n_val | Home MAE | Away MAE | Accuracy | Draw recall | Draw F1 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2002 | 2006 | 25 | 55 | 0.986 | 0.978 | 0.382 | 0.000 | 0.000 |
| 2 | 2002–2006 | 2010 | 80 | 55 | 0.910 | 0.777 | 0.418 | 0.133 | 0.154 |
| 3 | 2002–2010 | 2014 | 135 | 55 | 0.910 | 1.022 | 0.473 | 0.100 | 0.091 |
| 4 | 2002–2014 | 2018 | 190 | 55 | 1.019 | 0.773 | 0.436 | 0.222 | 0.160 |
| 5 | 2002–2018 | 2022 | 245 | 55 | 1.225 | 0.800 | 0.436 | 0.000 | 0.000 |
| 6 | 2002–2022 | 2026 (in-progress) | 300 | 76 | 1.216 | 0.866 | 0.461 | 0.045 | 0.077 |

**Mean ± std across folds (post-pruning)**: accuracy 0.4343 ± 0.0294, home MAE 1.0442 ± 0.1306, away MAE 0.8694 ± 0.0981, draw recall (mean) 0.0835, draw F1 (mean) 0.0803.

**Pre-pruning (163 features) for comparison**: accuracy 0.4357 ± 0.0369, home MAE 1.0403 ± 0.1271, away MAE 0.8685 ± 0.0975, draw recall (mean) 0.1344, draw F1 (mean) 0.1211.

Observations: CV accuracy and MAE are essentially unchanged by pruning (all deltas within ±0.004, noise-level on 6 folds), and **fold-to-fold accuracy std actually decreased** (0.0369 → 0.0294) — a genuine, if modest, generalization-variance improvement, which is the effect feature pruning is meant to produce. Mean draw recall across folds dropped (0.1344 → 0.0835), but per-fold inspection shows this is driven almost entirely by fold 4 (2018): draw recall 0.444 → 0.222, a single fold with only ~9 draw rows in its 55-row validation set — a small-sample artifact, not a broad regression (folds 1, 2, 3, 5, 6 are flat or trivially different). See "Empirical feature pruning" section below for the full accounting.

## Full-fit metrics (final model, 376 training rows) — POST-PRUNING

- Home goal MAE: **1.214** (was 1.219 pre-pruning), RMSE: **1.689** (was 1.704)
- Away goal MAE: **0.865** (was 0.855), RMSE: **1.136** (was 1.124)
- Regressor-derived result accuracy: **42.1%** (was 43.4%)
- Classifier raw accuracy: **47.4%** (was 36.8%) (draw-boosted: 28.9%, unchanged — see draw-handling trade-off above)
- Draw recall raw: **0.591** (was 0.182), Draw F1 raw: **0.456** (was 0.222)
- Mean Brier score (isotonic-calibrated): **0.199** (was 0.201) (Away Win 0.192, Draw 0.163, Home Win 0.241)
- Calibration ECE (isotonic): **0.086** (was 0.051 — worsened)

This single chronological holdout (76 rows, the actual 2026 completed matches) shows classifier accuracy and draw recall both improving markedly post-pruning, but — consistent with this report's opening caveat about wide standard errors on a small dataset — a single 76-row holdout is noisy, and the CV mean (6 folds, above) is the more trustworthy signal for whether pruning generalizes. The CV mean is flat; the single-holdout improvement should not be over-read as a guaranteed real-world gain. Calibration ECE genuinely worsened (0.051 → 0.086), a real (if still acceptable in absolute terms) trade-off — see below.

## Feature importance (top 10 of 134, XGBoost gain-based, post-pruning)
1. `attack_diff_10` (0.0205)
2. `away_max_unbeaten_streak_10` (0.0151)
3. `elo_difference` (0.0148) — **confirms the Elo-at-inference fix from the Feature Engineering wave is still working post-pruning**: this feature remains populated and meaningfully important.
4. `attack_diff_20` (0.0145)
5. `defense_diff_5` (0.0143)
6. `both_low_scoring_10` (0.0132)
7. `expected_total_goals_20` (0.0131)
8. `knockout_experience_diff` (0.0120) — the Feature Engineering wave's knockout-experience addition now ranks in the global top 10.
9. `away_goal_volatility_20` (0.0118)
10. `away_avg_opponent_elo_5` (0.0116)

No single feature dominates (top feature is only 2.1% of total gain, same as pre-pruning) — importance is still spread thin across the remaining 134 features. Removing the 29 zero/duplicate features did not concentrate importance onto fewer features in any material way, consistent with the removed features having contributed ~nothing to begin with.

## Empirical feature pruning (closes the previously-flagged gap)

**This section replaces the "Known gap" note from the 2026-07-03 version of
this report.** The empirical SHAP/permutation-importance/correlation/
mutual-information/variance audit was completed against the actual trained
163-feature production model (not estimated), using the full 376-row
training matrix reconstructed exactly (verified to match the saved model's
`feature_columns` list column-for-column before running any analysis).

**Result: 29 of 163 features removed** (163 → 134). Full per-feature
evidence (SHAP values, permutation importance, correlation coefficients,
variance/near-constant checks) is in `FEATURE_ENGINEERING.md` §5 — summary:

- **21 exact algebraic duplicates** (Pearson r = 1.000000, not merely
  "high" correlation): `{side}_attack_momentum_{w}` ≡
  `{side}_avg_goals_scored_{w}`, `{side}_defense_momentum_{w}` ≡
  `{side}_avg_goals_conceded_{w}`, `{side}_tournament_experience_{w}` ≡
  `{side}_matches_played_{w}` (all 3 windows × 2 sides each = 18), plus
  `momentum_diff_{w}` ≡ `goal_diff_diff_{w}` (3 windows).
- **2 true zero-variance constants**: `neutral_venue`, `tournament_weight`
  — both exactly one distinct value across all 376 rows (WC-only corpus
  means every row is `tournament="FIFA World Cup"`,
  `neutral_venue=True`), confirmed 0.0 SHAP and 0.0 permutation importance
  in every one of the 3 models (home regressor, away regressor, result
  classifier).
- **6 near-zero-variance, zero-importance features**: `{side}_upset_score_{w}`
  (all 3 windows × 2 sides) — 97.9-98.7% of rows exactly 0.0, and
  independently confirmed 0.0 SHAP and 0.0 permutation importance across
  all 3 models (not pruned on variance alone).

**What was explicitly NOT pruned, and why**: a stricter test (SHAP < 1e-6
AND permutation importance < 1e-6 AND mutual information < 0.01, all three
agreeing) flagged only 11 features total — the 8 above plus 3 more
(`home_max_win_streak_5`, `home_current_conceding_streak_20`,
`away_current_conceding_streak_20`). Those 3 were checked individually:
all have healthy variance (1.5-4.7) and multiple distinct values, with no
exact-duplicate partner in the correlation matrix — they simply weren't
selected by any split in *this particular* trained model (expected when
163 correlated features compete for splits under
`colsample_bytree=0.85`/`subsample=0.85` on 376 rows). These were
deliberately left in rather than removed on a single model's zero
split-usage alone, per this task's explicit instruction to err toward
under-pruning on a small dataset. A broader ~37-feature set showed zero
SHAP and zero permutation importance without MI corroboration; the same
reasoning kept those in too — no single measure, on its own, was treated
as sufficient grounds for removal.

**Retrain and comparison**: the model was retrained after pruning, reusing
the exact same methodology (expanding-window walk-forward CV, Optuna-tuned
hyperparameters from the existing `best_params.json` — not re-searched,
isotonic calibration). See the CV table and full-fit metrics above for the
complete before/after numbers.

**Honest verdict**: pruning is **neutral-to-mildly-positive** for
generalization, not a large win and not a loss. CV-mean accuracy and MAE
are unchanged within noise; CV fold-to-fold accuracy variance decreased
(a real, if modest, sign of reduced overfitting risk, which was the goal);
calibration Brier improved marginally while ECE worsened; the apparent
draw-recall regression in the CV mean is a single-fold artifact, not a
systemic effect. Given 29 fewer features carrying zero verified signal (21
of them literally the same number as a feature already kept) and no
metric moving in a clearly worse direction on the more trustworthy
CV-mean numbers, the pruned 134-feature model was kept as the production
model. The removed features cost nothing to drop and reduce the
overfitting surface on a 376-row corpus, which is the generalization
argument the task asked to prioritize over chasing a specific accuracy
number.

**Rollback path**: the pre-pruning 163-feature model, scaler, and all
reports are preserved as `*.prepruning.bak` in `backend/app/ml/models/`
(distinct from the older `*.bak` files, which are the original
pre-WC-retrain 141-feature model — see "Old vs. new model comparison"
below).

## Old vs. new model comparison
The previous production model (`xgboost_model.pkl.bak`, `scaler.pkl.bak`, both preserved for rollback) was trained on a much larger, broader "all competitions 1872–2017" dataset (thousands of matches across all competition types, not WC-only). A rigorous apples-to-apples re-evaluation of the old model on this new WC-only holdout was not performed (the old model's feature schema and scaler differ from the new one, so it can't be run through the new feature pipeline directly without reconstructing its exact original input format) — flagged here as a genuine gap rather than asserting a comparison that wasn't actually run.

What can be said honestly:
- **Old model**: trained on a much larger sample (likely low thousands of matches) spanning many competition types — better statistical power, but training distribution includes many non-World-Cup match dynamics (friendlies, qualifiers, continental cups) that may not transfer perfectly to World Cup knockout-stakes matches.
- **New model**: trained on far fewer samples (376) but exclusively on real World Cup matches, including 89 real 2026 matches with genuine in-tournament signal (current form, current Elo, current rankings) that the old model could never have seen. Narrower but more contextually relevant data, at the cost of statistical power and higher variance in the metrics above.
- This is a real trade-off, not a strict improvement — smaller-but-relevant vs. larger-but-broader. The wide fold-to-fold variance in the CV table above (draw recall ranging 0.0–0.44) is the direct fingerprint of the small-sample cost.

## Recommendations for next steps
1. ~~Complete the deferred empirical feature-pruning pass~~ — **done**, see "Empirical feature pruning" above (163 → 134 features, neutral-to-mildly-positive result).
2. Consider whether blending in the old broader dataset as auxiliary pretraining (not replacing the WC-only fine-tuning) could reduce variance without losing WC-specific relevance — a design question for the user/team, not something to decide unilaterally.
3. Re-run the draw-boost trade-off analysis with more data before treating 1.05 as final; the current setting near-maximizes recall at a real precision cost.
4. Do a proper old-vs-new apples-to-apples comparison once there's time to reconstruct the old feature/scaler pipeline, rather than the qualitative comparison given above.
5. Calibration ECE worsened post-pruning (0.051 → 0.086) even though Brier improved slightly — worth a closer look with more calibration data before the next retrain, since ECE and Brier disagreeing on direction is itself a signal that the isotonic calibrator is working with a very small calibration set (45 validation rows).
