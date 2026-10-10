# V3 benchmark

Corpus `b38434f8f74cd9fa` · pipeline 3.0.0 · seed 42

All figures are out-of-sample. Probabilities are temperature-scaled on a validation period that precedes the test period. Lower is better for log loss, Brier and RPS.

## Development fold 2010-2013

| Model | n | Log loss | Brier | RPS | Accuracy | Draw recall | Goal MAE | ECE |
|---|---|---|---|---|---|---|---|---|
| prior | 3970 | 1.0520 | 0.6341 | 0.2273 | 0.483 | 0.000 | — | 0.033 |
| elo_ordered_logit | 3970 | 0.9030 | 0.5338 | 0.1793 | 0.581 | 0.000 | — | 0.009 |
| poisson | 3970 | 0.8928 | 0.5274 | 0.1766 | 0.582 | 0.000 | 0.959 | 0.015 |
| poisson_dc | 3970 | 0.8920 | 0.5270 | 0.1765 | 0.582 | 0.001 | 0.959 | 0.009 |
| multinomial_logit | 3970 | 0.8915 | 0.5261 | 0.1761 | 0.581 | 0.085 | — | 0.019 |
| xgboost | 3970 | 0.8927 | 0.5273 | 0.1764 | 0.581 | 0.040 | — | 0.021 |
| ens_elo+poisson[equal] | 3970 | 0.8943 | 0.5283 | 0.1771 | 0.580 | 0.000 | — | 0.016 |
| ens_elo+poisson[fitted] | 3970 | 0.8939 | 0.5281 | 0.1769 | 0.580 | 0.000 | — | 0.015 |
| ens_poisson+xgb[equal] | 3970 | 0.8896 | 0.5255 | 0.1759 | 0.580 | 0.003 | — | 0.016 |
| ens_poisson+xgb[fitted] | 3970 | 0.8910 | 0.5263 | 0.1761 | 0.580 | 0.021 | — | 0.019 |
| ens_poisson+mlr+xgb[equal] | 3970 | 0.8893 | 0.5252 | 0.1758 | 0.579 | 0.013 | — | 0.015 |
| ens_poisson+mlr+xgb[fitted] | 3970 | 0.8910 | 0.5263 | 0.1761 | 0.580 | 0.021 | — | 0.019 |

## Development fold 2014-2017

| Model | n | Log loss | Brier | RPS | Accuracy | Draw recall | Goal MAE | ECE |
|---|---|---|---|---|---|---|---|---|
| prior | 3739 | 1.0483 | 0.6314 | 0.2263 | 0.475 | 0.000 | — | 0.003 |
| elo_ordered_logit | 3739 | 0.8991 | 0.5289 | 0.1778 | 0.587 | 0.000 | — | 0.015 |
| poisson | 3739 | 0.8898 | 0.5229 | 0.1751 | 0.590 | 0.000 | 0.9376 | 0.023 |
| poisson_dc | 3739 | 0.8893 | 0.5224 | 0.1751 | 0.590 | 0.002 | 0.9376 | 0.021 |
| multinomial_logit | 3739 | 0.8884 | 0.5220 | 0.1750 | 0.589 | 0.060 | — | 0.016 |
| xgboost | 3739 | 0.8932 | 0.5252 | 0.1763 | 0.587 | 0.015 | — | 0.017 |
| ens_elo+poisson[equal] | 3739 | 0.8909 | 0.5238 | 0.1756 | 0.591 | 0.000 | — | 0.012 |
| ens_elo+poisson[fitted] | 3739 | 0.8893 | 0.5224 | 0.1751 | 0.590 | 0.002 | — | 0.021 |
| ens_poisson+xgb[equal] | 3739 | 0.8891 | 0.5226 | 0.1753 | 0.590 | 0.001 | — | 0.016 |
| ens_poisson+xgb[fitted] | 3739 | 0.8911 | 0.5239 | 0.1758 | 0.590 | 0.009 | — | 0.017 |
| ens_poisson+mlr+xgb[equal] | 3739 | 0.8880 | 0.5220 | 0.1751 | 0.593 | 0.019 | — | 0.018 |
| ens_poisson+mlr+xgb[fitted] | 3739 | 0.8911 | 0.5239 | 0.1758 | 0.590 | 0.009 | — | 0.017 |

## Development fold 2018-2021

| Model | n | Log loss | Brier | RPS | Accuracy | Draw recall | Goal MAE | ECE |
|---|---|---|---|---|---|---|---|---|
| prior | 3562 | 1.0465 | 0.6303 | 0.2262 | 0.477 | 0.000 | — | 0.010 |
| elo_ordered_logit | 3562 | 0.8611 | 0.5059 | 0.1671 | 0.606 | 0.000 | — | 0.011 |
| poisson | 3562 | 0.8553 | 0.5028 | 0.1659 | 0.604 | 0.000 | 0.9396 | 0.018 |
| poisson_dc | 3562 | 0.8538 | 0.5021 | 0.1658 | 0.604 | 0.000 | 0.9396 | 0.018 |
| multinomial_logit | 3562 | 0.8536 | 0.5019 | 0.1658 | 0.604 | 0.051 | — | 0.010 |
| xgboost | 3562 | 0.8518 | 0.5011 | 0.1654 | 0.606 | 0.002 | — | 0.019 |
| ens_elo+poisson[equal] | 3562 | 0.8542 | 0.5020 | 0.1656 | 0.607 | 0.000 | — | 0.013 |
| ens_elo+poisson[fitted] | 3562 | 0.8533 | 0.5017 | 0.1656 | 0.605 | 0.000 | — | 0.018 |
| ens_poisson+xgb[equal] | 3562 | 0.8509 | 0.5007 | 0.1652 | 0.606 | 0.000 | — | 0.010 |
| ens_poisson+xgb[fitted] | 3562 | 0.8513 | 0.5009 | 0.1653 | 0.606 | 0.000 | — | 0.010 |
| ens_poisson+mlr+xgb[equal] | 3562 | 0.8510 | 0.5007 | 0.1653 | 0.609 | 0.007 | — | 0.008 |
| ens_poisson+mlr+xgb[fitted] | 3562 | 0.8527 | 0.5015 | 0.1656 | 0.604 | 0.035 | — | 0.009 |

## Development fold 2022-2025

| Model | n | Log loss | Brier | RPS | Accuracy | Draw recall | Goal MAE | ECE |
|---|---|---|---|---|---|---|---|---|
| prior | 4267 | 1.0483 | 0.6315 | 0.2277 | 0.477 | 0.000 | — | 0.011 |
| elo_ordered_logit | 4267 | 0.8732 | 0.5138 | 0.1714 | 0.603 | 0.000 | — | 0.024 |
| poisson | 4267 | 0.8672 | 0.5093 | 0.1698 | 0.605 | 0.000 | 0.9252 | 0.026 |
| poisson_dc | 4267 | 0.8667 | 0.5088 | 0.1698 | 0.605 | 0.000 | 0.9252 | 0.026 |
| multinomial_logit | 4267 | 0.8668 | 0.5093 | 0.1699 | 0.606 | 0.043 | — | 0.025 |
| xgboost | 4267 | 0.8664 | 0.5096 | 0.1698 | 0.604 | 0.001 | — | 0.026 |
| ens_elo+poisson[equal] | 4267 | 0.8667 | 0.5095 | 0.1699 | 0.603 | 0.000 | — | 0.026 |
| ens_elo+poisson[fitted] | 4267 | 0.8660 | 0.5086 | 0.1697 | 0.604 | 0.000 | — | 0.025 |
| ens_poisson+xgb[equal] | 4267 | 0.8648 | 0.5085 | 0.1695 | 0.605 | 0.000 | — | 0.028 |
| ens_poisson+xgb[fitted] | 4267 | 0.8652 | 0.5085 | 0.1696 | 0.605 | 0.000 | — | 0.027 |
| ens_poisson+mlr+xgb[equal] | 4267 | 0.8648 | 0.5085 | 0.1696 | 0.604 | 0.005 | — | 0.028 |
| ens_poisson+mlr+xgb[fitted] | 4267 | 0.8652 | 0.5084 | 0.1696 | 0.605 | 0.002 | — | 0.028 |

## Mean development log loss

| Model | Mean log loss |
|---|---|
| ens_poisson+mlr+xgb[equal] | 0.87328 |
| ens_poisson+xgb[equal] | 0.87361 |
| ens_poisson+xgb[fitted] | 0.87467 |
| ens_poisson+mlr+xgb[fitted] | 0.87502 |
| multinomial_logit | 0.87507 |
| poisson_dc | 0.87543 |
| ens_elo+poisson[fitted] | 0.87560 |
| xgboost | 0.87599 |
| poisson | 0.87626 |
| ens_elo+poisson[equal] | 0.87651 |
| elo_ordered_logit | 0.88411 |
| prior | 1.04879 |

**Selected: `ens_poisson+xgb[equal]`** — lowest mean dev-fold log loss after temperature scaling; candidates within the tie margin are treated as equal and the simplest is chosen. Within the tie margin (0.001): ens_poisson+mlr+xgb[equal], ens_poisson+xgb[equal].

## Calibration method (mean development log loss, all non-baseline models)

| Method | Mean log loss |
|---|---|
| none | 0.87704 |
| temperature | 0.87737 |
| sigmoid | 0.87755 |
| isotonic | 0.92984 |

## Final test — all 2026 matches (untouched until selection was complete)

| Model | n | Log loss | Brier | RPS | Accuracy | Draw recall | Goal MAE | ECE |
|---|---|---|---|---|---|---|---|---|
| prior | 801 | 1.0500 | 0.6333 | 0.2294 | 0.478 | 0.000 | — | 0.026 |
| elo_ordered_logit | 801 | 0.8814 | 0.5170 | 0.1739 | 0.602 | 0.000 | — | 0.032 |
| poisson | 801 | 0.8761 | 0.5134 | 0.1726 | 0.616 | 0.000 | 0.9477 | 0.022 |
| poisson_dc | 801 | 0.8754 | 0.5130 | 0.1725 | 0.616 | 0.000 | 0.9477 | 0.021 |
| multinomial_logit | 801 | 0.8773 | 0.5134 | 0.1732 | 0.603 | 0.017 | — | 0.034 |
| xgboost | 801 | 0.8742 | 0.5124 | 0.1727 | 0.607 | 0.000 | — | 0.024 |
| ens_elo+poisson[equal] | 801 | 0.8753 | 0.5130 | 0.1724 | 0.611 | 0.000 | — | 0.032 |
| ens_elo+poisson[fitted] | 801 | 0.8746 | 0.5125 | 0.1722 | 0.611 | 0.000 | — | 0.028 |
| ens_poisson+xgb[equal] | 801 | 0.8733 | 0.5119 | 0.1723 | 0.609 | 0.000 | — | 0.034 |
| ens_poisson+xgb[fitted] | 801 | 0.8735 | 0.5120 | 0.1723 | 0.609 | 0.000 | — | 0.039 |
| ens_poisson+mlr+xgb[equal] | 801 | 0.8739 | 0.5120 | 0.1725 | 0.608 | 0.000 | — | 0.030 |
| ens_poisson+mlr+xgb[fitted] | 801 | 0.8740 | 0.5120 | 0.1725 | 0.608 | 0.000 | — | 0.027 |

## Final test — World Cup 2026 only

| Model | n | Log loss | Brier | RPS | Accuracy | Draw recall | Goal MAE | ECE |
|---|---|---|---|---|---|---|---|---|
| prior | 104 | 1.0675 | 0.6456 | 0.2339 | 0.471 | 0.000 | — | 0.074 |
| elo_ordered_logit | 104 | 0.8541 | 0.5002 | 0.1603 | 0.644 | 0.000 | — | 0.105 |
| poisson | 104 | 0.8549 | 0.5003 | 0.1607 | 0.683 | 0.000 | — | 0.132 |
| poisson_dc | 104 | 0.8517 | 0.4998 | 0.1603 | 0.683 | 0.000 | — | 0.135 |
| multinomial_logit | 104 | 0.8485 | 0.4948 | 0.1587 | 0.673 | 0.000 | — | 0.124 |
| xgboost | 104 | 0.8556 | 0.5008 | 0.1607 | 0.663 | 0.000 | — | 0.133 |
| ens_elo+poisson[equal] | 104 | 0.8486 | 0.4970 | 0.1590 | 0.663 | 0.000 | — | 0.126 |
| ens_elo+poisson[fitted] | 104 | 0.8492 | 0.4978 | 0.1593 | 0.654 | 0.000 | — | 0.131 |
| ens_poisson+xgb[equal] | 104 | 0.8519 | 0.4991 | 0.1599 | 0.654 | 0.000 | — | 0.144 |
| ens_poisson+xgb[fitted] | 104 | 0.8516 | 0.4990 | 0.1599 | 0.654 | 0.000 | — | 0.141 |
| ens_poisson+mlr+xgb[equal] | 104 | 0.8503 | 0.4973 | 0.1593 | 0.654 | 0.000 | — | 0.137 |
| ens_poisson+mlr+xgb[fitted] | 104 | 0.8500 | 0.4973 | 0.1593 | 0.654 | 0.000 | — | 0.115 |

## Selected model on the final test

- All 2026: {"n": 801, "log_loss": 0.87332, "brier": 0.51185, "rps": 0.17229, "accuracy": 0.6092, "draw_recall": 0.0, "draw_precision": 0.0, "mean_p_draw": 0.2293, "ece": 0.0344, "classwise_ece": 0.0322, "goal_mae": 0.9477, "goal_rmse": 1.2571}
- World Cup 2026: {"n": 104, "log_loss": 0.85193, "brier": 0.49913, "rps": 0.15994, "accuracy": 0.6538, "draw_recall": 0.0, "draw_precision": 0.0, "mean_p_draw": 0.2293, "ece": 0.1441, "classwise_ece": 0.0859, "goal_mae": 0.9087, "goal_rmse": 1.2192}
- Log-loss difference vs class prior (all 2026): {"mean_diff": -0.17664, "ci95": [-0.20922, -0.14435], "significant": true}
- Log-loss difference vs Elo (all 2026): {"mean_diff": -0.00808, "ci95": [-0.0163, 0.00043], "significant": false}
- vs class prior (World Cup): {"mean_diff": -0.21555, "ci95": [-0.28633, -0.13492], "significant": true}
- vs Elo (World Cup): {"mean_diff": -0.0022, "ci95": [-0.02496, 0.01981], "significant": false}
