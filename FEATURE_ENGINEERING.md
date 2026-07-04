# Feature Engineering — Full Audit

Covers `backend/app/ml/features/feature_engineering.py` (and its two call
sites, `backend/app/ml/train.py` and `backend/app/ml/data/loader.py`) as of
this pass: the pre-existing feature set, the Elo-at-inference fix (full
detail in `ELO_SYSTEM.md`), the new features added this pass (full detail on
rankings in `RANKINGS_INTEGRATION.md`), and — for every candidate feature
named in the audit brief — an explicit include/exclude decision with the
statistic that drove it.

`build_feature_vector()` now produces **134 columns** per matchup (was 156
before the Feature Engineering wave's additions, then 163 after 7 new columns
were added; a subsequent **empirical pruning pass**, detailed in §5 below,
removed 29 of those 163 with evidence, landing at 134).

---

## 1. Existing feature set (kept, unmodified logic)

Grouped by family. `{w}` = one of the three rolling windows, `ROLLING_WINDOWS
= [5, 10, 20]`.

### 1.1 Rolling form (`compute_team_rolling_stats`, per side per window)
`{side}_weighted_points_{w}`, `{side}_avg_goals_scored_{w}`,
`{side}_avg_goals_conceded_{w}`, `{side}_attack_strength_{w}`,
`{side}_defense_strength_{w}`, `{side}_momentum_{w}`,
`{side}_attack_momentum_{w}`, `{side}_defense_momentum_{w}`,
`{side}_clean_sheet_rate_{w}`, `{side}_goal_volatility_{w}`,
`{side}_max_win_streak_{w}`, `{side}_max_unbeaten_streak_{w}`,
`{side}_current_scoring_streak_{w}`, `{side}_current_conceding_streak_{w}`,
`{side}_avg_opponent_elo_{w}`, `{side}_tournament_experience_{w}`,
`{side}_home_advantage_strength_{w}`, `{side}_upset_score_{w}`,
`{side}_high_scoring_rate_{w}`, `{side}_matches_played_{w}`.

Weighted by tournament importance × recency-within-window × 3-year
exponential time decay. This is the largest feature family (20 stats × 2
sides × 3 windows = 120 columns) and already covers "recent form (last 5,
last 10)", "goals scored/conceded, average goals, goal difference" (via
`goal_diff_diff_{w}`, see §1.4), and a good chunk of "rolling team strength"
(attack/defense strength are already a rolling strength index — see §3 for
why a separate blended strength feature was NOT added on top).

### 1.2 Elo (`compute_dynamic_elo`, `_latest_elo_for_team`)
`home_elo`, `away_elo`, `elo_difference`, `elo_closeness`, `elo_abs_diff`.
See `ELO_SYSTEM.md` for the full write-up, including the inference-time bug
fix applied in this pass.

### 1.3 Rest days / fatigue (`compute_rest_days`)
`home_rest_days`, `away_rest_days`, `rest_day_diff`. This already **is**
"days since last match" from the audit list — no new feature needed.

### 1.4 Derived differentials
`goal_diff_diff_{w}`, `attack_diff_{w}`, `defense_diff_{w}`,
`momentum_diff_{w}` (per window) — cross-team differences of the rolling
stats above.

### 1.5 Draw-predictive interactions
`both_defensive_{w}`, `both_low_scoring_{w}`, `form_convergence_{w}`,
`expected_total_goals_{w}` (per window).

### 1.6 Head-to-head (`compute_head_to_head`)
`h2h_home_win_rate`, `h2h_avg_goals` — already satisfies "head-to-head
record" from the audit list.

### 1.7 Match context
`neutral_venue` (already satisfies "home advantage / neutral venue flag"),
`tournament_weight` (already satisfies "tournament importance / stage
weighting" — derived from `TOURNAMENT_WEIGHTS`, a lookup by tournament
name/text match, not by knockout stage specifically — see §2.3 for the
stage-specific addition made this pass).

---

## 2. New features added this pass

### 2.1 `home_fifa_rank`, `away_fifa_rank`, `fifa_rank_diff`
Source: `teams_reference.csv.fifa_ranking_pre_tournament`. Full design
rationale, missing-data handling, and why this is kept separate from Elo
(not blended) in `RANKINGS_INTEGRATION.md`. **Justification:** the audit
brief explicitly asked for "Current FIFA Ranking, FIFA Ranking Points" as a
complement to Elo — FIFA's official ranking uses a different, committee-
governed methodology than a from-scratch dynamic Elo computed only from
this app's own match table, so it is a genuinely independent signal, not a
duplicate. NaN (not fabricated) for the ~25 historical-only teams not in the
48-team 2026 reference — checked directly (see `RANKINGS_INTEGRATION.md`
§5), not assumed.

### 2.2 `same_confederation`
Source: `teams_reference.csv.confederation`. **Justification:** checked
distribution first — 6 confederations across the 48 teams (UEFA 16, CAF 10,
AFC 9, CONCACAF 6, CONMEBOL 6, OFC 1), a real, non-degenerate spread, not a
near-constant. A same/different flag is the most direct, lowest-dimensional
way to let the model test "do same-confederation matchups behave
differently" without adding 5 extra one-hot columns of uncertain marginal
value (see `RANKINGS_INTEGRATION.md` §3 for the one-hot-vs-flag tradeoff
considered). Raw confederation identity itself is **not** added as a
feature — nominal/nonlinear-in-team-space, and the specific hypothesis
worth testing is captured by the flag, not by which confederation each side
happens to be in.

### 2.3 `home_knockout_experience`, `away_knockout_experience`, `knockout_experience_diff`
Source: newly-added `stage` column now selected by both
`loader.py`'s and `train.py`'s SQL queries (previously not selected at all,
even though `matches.stage` already existed on the DB schema — this was a
plain projection gap, not a schema change). `compute_knockout_experience()`
counts each team's prior matches at `round_of_32` and beyond (via
`KNOCKOUT_STAGES`), strictly before the match date, using the same
`team_index` scan pattern as `compute_rest_days`.

**Justification — checked variance before deciding, not assumed:**

```
Knockout appearances (2002-2022 WC data) among the 48 WC2026 teams:
  mean = 3.79, variance = 17.9, 35 / 48 teams have at least one appearance
  Top 3: Brazil (16), Germany (15), France (14)
```

35 of 48 teams have non-zero knockout experience and the spread has real
variance (std ≈ 4.2 matches) — a legitimate signal distinguishing
tournament-tested sides from teams with a thin or nonexistent knockout
record, independent of what Elo/rolling-form already capture (a team can
have strong recent *form* without ever having faced the pressure of a
knockout match). **Caveat flagged for the ML Engineering wave:** this is
counted only from `matches_historical.csv`'s 2002-2022 rows via the
`matches.stage` column — coverage is only as good as `stage` being
populated on the DB `matches` table for older, non-WC seed data (see
`KNOWN_ASSUMPTIONS.md` re: legacy seed data). `compute_knockout_experience`
returns `0.0` (not NaN, not an error) when the `stage` column is entirely
absent from a given DataFrame, so this degrades gracefully rather than
breaking on older-shaped test fixtures.

---

## 3. Candidates considered and explicitly excluded (with the stat that drove it)

| Candidate | Decision | Why |
|---|---|---|
| **World Cup titles** | **Excluded** | Checked directly: among the 48 WC2026 teams, only 4 have ever won a title in the 2002-2022 window covered by `matches_historical.csv` (Brazil, Spain, Germany, France) — mean 0.083, variance 0.076, **44/48 teams show a flat 0**. Near-zero variance across the field, and the 4 teams that do have titles are already near the top of both Elo and FIFA ranking, so the marginal information beyond those two features is minimal for the vast majority of the 2026 field. Not added; can be trivially added later as a plain count from the same `stage=='final'` + winner logic if the ML Engineering wave's empirical pruning pass wants to test it. |
| **Rolling team strength (as a distinct new feature)** | **Excluded — already covered** | `home_attack_strength_{w}` / `home_defense_strength_{w}` (existing, §1.1) already **are** a rolling strength index (goals-scored/conceded relative to `GLOBAL_AVG_GOALS`, time-decayed). Adding a further "blended" strength score (e.g. attack+defense+Elo combined into one number) would (a) duplicate existing signal the model can already combine on its own via tree splits, and (b) pre-judge a blend weighting with no trained-model evidence behind it — same objection as blending Elo+ranking in `RANKINGS_INTEGRATION.md` §3. Left to the model to combine, not pre-combined here. |
| **`match_team_stats.csv` box-score stats** (possession, shots, corners, fouls, etc.) | **Excluded** | Two independent reasons, checked directly: (1) **Coverage** — only 66 of 419 historical matches (66/419 ≈ 16%) have any box-score row at all (`match_team_stats.csv` only covers 2026 matches, 132 rows / 2 teams per match = 66 matches), so any rolling feature built from it would be `NaN` for ~84% of training rows — far too sparse to be a reliable pre-match feature for a model trained mostly on 2002-2022 data. (2) **Leakage risk, structurally** — possession/shots/corners are *in-match outcome stats* for the very match being predicted, not known before kickoff; the only legitimate use would be as *historical* rolling inputs (e.g. "team's average possession over its last 5 matches"), which circles back to problem (1)'s sparsity. Not added. |
| **Days since last match** | **N/A — already exists** | This is `home_rest_days`/`away_rest_days`/`rest_day_diff` (§1.3), already implemented pre-audit. No new feature added; confirmed it satisfies the audit item as-is. |
| **Confederation (raw identity)** | **Partially excluded** | See §2.2 — the derived `same_confederation` flag was added; raw per-team confederation strings were not, for the reasons given there. |

---

## 5. Empirical feature pruning (ML Engineering wave)

This section documents the empirical audit that closes the gap flagged in
`MODEL_EVALUATION.md`'s "Known gap" section: the 163-feature model was
audited with SHAP, permutation importance, pairwise correlation, mutual
information, and variance analysis, all computed against the actual trained
production model (`xgboost_model.pkl`, 376 training rows) — not estimated or
inferred. Full methodology, retrain, and metric comparison in
`MODEL_EVALUATION.md` §"Empirical feature pruning".

**29 of 163 features were removed.** Every removal falls into one of two
evidence categories, both checked directly on the reconstructed 163-column
training matrix:

### 5.1 Exact algebraic duplicates (Pearson r = 1.000000, 21 features removed)

| Removed | Kept (identical) | Why identical |
|---|---|---|
| `{side}_attack_momentum_{w}` (6: home/away × 5/10/20) | `{side}_avg_goals_scored_{w}` | Both accumulate `gs * weight` inside `compute_team_rolling_stats` — the same sum divided by the same normalizer. Not "highly correlated", **the same number**, verified r=1.000000 to 6 decimal places on all 376 rows, all 3 windows. |
| `{side}_defense_momentum_{w}` (6) | `{side}_avg_goals_conceded_{w}` | Same reasoning, `gc * weight` accumulator. |
| `{side}_tournament_experience_{w}` (6) | `{side}_matches_played_{w}` | `tournament_experience` counts matches with `tournament_w >= 0.80`; every row in `matches_historical.csv` is `"FIFA World Cup"` (weight 1.00, always ≥ 0.80), so the count degenerates to a plain match count — identical to `matches_played_{w}` on this WC-only corpus. r=1.000000. |
| `momentum_diff_{w}` (3: windows 5/10/20) | `goal_diff_diff_{w}` | Algebraically: `home_momentum_w - away_momentum_w = (home_avg_goals_scored_w - home_avg_goals_conceded_w) - (away_avg_goals_scored_w - away_avg_goals_conceded_w) = goal_diff_diff_w`. r=1.000000; max absolute difference across all 376 rows was ~1e-15 (floating-point noise only). |

`goal_diff_diff_{w}` and `avg_goals_scored/conceded_{w}` were kept over their
momentum-named duplicates because SHAP mean(|value|) was equal-or-higher for
the kept side in every case, and the names are the clearer description of
what's actually measured.

### 5.2 Zero/near-zero variance AND zero importance across all 3 measures (8 features removed)

| Removed | Variance evidence | SHAP (home/away/result) | Permutation importance (home/away/result) |
|---|---|---|---|
| `neutral_venue` | var = 0.0 exactly, 100% of rows = 1.0 (single value) — `load_data()` hardcodes `neutral_venue=True` for every row since the corpus is WC-only | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 |
| `tournament_weight` | var = 0.0 exactly, 100% of rows = 1.00 — every row's tournament is `"FIFA World Cup"` (weight 1.00) | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 |
| `home_upset_score_5` | 98.7% of rows exactly 0.0, only 6 distinct values, var=0.0036 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 |
| `away_upset_score_5` | 98.7% zero, 6 distinct values, var=0.0025 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 |
| `home_upset_score_10` | 98.1% zero, 8 distinct values, var=0.0024 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 |
| `away_upset_score_10` | 97.9% zero, 9 distinct values, var=0.0018 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 |
| `home_upset_score_20` | 98.1% zero, 8 distinct values, var=0.0019 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 |
| `away_upset_score_20` | 97.9% zero, 9 distinct values, var=0.0015 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 |

`neutral_venue`/`tournament_weight` are true constants (var exactly 0.0) —
a tree model cannot split on a column with a single value, full stop.
`upset_score_{w}` is not a hard constant, but is a rare-event indicator
(beating an opponent rated 100+ Elo higher) that is ≥97.9% zero in a
376-row corpus, and — critically — was checked against SHAP *and*
permutation importance on the real trained model, not just variance in
isolation: both measures independently confirm the model derives zero
predictive use from any of the 6 window/side variants. Mutual information
against goals was also checked for these (values in the 0.0–0.13 range,
i.e. low but not exactly zero — expected, since MI measures raw
association in the data and doesn't know what the specific trained model
chose to use); this is exactly the "if a feature has weak importance but
isn't clearly redundant/harmful, consider leaving it" caution applied in
reverse — these *were* removed because all three signals (SHAP,
permutation importance, and near-zero variance) agreed, not on variance
alone.

### 5.3 Candidates considered and explicitly NOT pruned (evidence against removal)

A stricter "all three of SHAP, permutation importance, and mutual
information near zero" test (SHAP < 1e-6 AND permutation importance < 1e-6
AND MI < 0.01) flagged only 11 features total — the 8 above, plus 3 more:
`home_max_win_streak_5`, `home_current_conceding_streak_20`,
`away_current_conceding_streak_20`. These 3 were checked individually and
**kept**, not removed:

- `home_max_win_streak_5`: variance 1.51, 6 distinct values, no clean
  correlated duplicate found (checked against the full |r|>0.9 pair list).
- `home_current_conceding_streak_20` / `away_current_conceding_streak_20`:
  variance 4.37 / 4.69, 12-14 distinct values, likewise no duplicate.

None of these three are near-constant or algebraically redundant — they
simply weren't selected by any tree split in *this specific* trained model,
which is expected background noise when 163 correlated features compete for
splits on only 376 rows (the tuned regressors use
`colsample_bytree=0.9314`/`subsample=0.9997`, and the classifier uses
`colsample_bytree=0.6192`/`subsample=0.6352` — see `best_params.json`; many
features never get a chance to be tried in any given tree regardless of the
exact subsampling rate). Per the task's
explicit caution against over-pruning a small dataset, these were left in
rather than removed on model-specific SHAP/permutation zero-outs alone,
since a re-trained model with a different random seed or slightly different
hyperparameters could easily select them instead. A broader ~37-feature set
showed SHAP=0 AND permutation=0 (but not checked against MI) — the same
reasoning applies: without corroboration from a second, independent signal
(correlation-based redundancy or true near-zero variance), a single
model's zero split-usage is not strong enough evidence to discard a
feature from a 376-row corpus.

## 6. What was NOT touched

- `tournament_simulator.py`, database schema/SQL, and API endpoint code —
  explicitly out of scope for this pass (owned by other agents in this
  wave).
- No existing feature's *computation logic* was changed (only additive
  columns). The one non-additive-looking change — `loader.py` and
  `train.py`'s SQL now selecting `m.stage` — is a projection addition only
  (the column already existed on the `matches` table); no schema/migration
  file was touched.
- Final **empirical** feature pruning (removing features that hurt
  validation performance, via SHAP/permutation importance on a freshly
  retrained model) was originally left to the next wave (ML Engineering) —
  see §5 above for that completed pass, run against the actual trained
  163-feature production model, not estimated.

## 7. Test suite status

`cd backend && pytest -q` → **52 passed** after the original Feature
Engineering pass (Elo fix + rankings + knockout experience), and **80
passed** after the ML Engineering wave's empirical pruning pass (§5) and
subsequent retrain — no regressions at either point.
