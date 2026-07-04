# FIFA Rankings Integration

Documents how `backend/app/data/processed/teams_reference.csv` (the Data
Engineering wave's 48-team WC2026 reference file) is wired into feature
engineering as a **complement to**, not a replacement for, the Elo system
described in `ELO_SYSTEM.md`.

---

## 1. Source data

`backend/app/data/processed/teams_reference.csv` — 48 rows, one per 2026
World Cup team:

```
canonical_name, fifa_code, group, confederation, fifa_ranking_pre_tournament, elo_rating
```

Notes on reading it correctly:

- **UTF-8 BOM**: the file is Excel-exported and starts with a BOM. It must
  be read with `encoding="utf-8-sig"` — reading with plain `utf-8` silently
  renames the first column to `"﻿canonical_name"`, and every dict-based
  lookup keyed on `"canonical_name"` then misses 100% of the time with no
  error. `feature_engineering.py::_load_teams_reference()` does this
  correctly.
- **Only 48 teams.** This file covers exactly the 2026 tournament field. It
  does **not** cover the ~25 additional nations that appear as historical
  opponents in `matches_historical.csv`'s 2002-2022 rows (e.g. Republic of
  Ireland, Denmark, Poland, Costa Rica, Serbia and Montenegro — see below
  for the full gap).
- `elo_rating` in this file is a separate, static pre-tournament Elo
  snapshot — it is **not** used by the dynamic Elo system in
  `ELO_SYSTEM.md` (which computes its own rolling Elo from match history).
  We deliberately do not feed this column into feature engineering as a
  competing "Elo" signal — see §4.

## 2. Design: where the lookup lives, and why it's swappable

`backend/app/ml/features/feature_engineering.py` adds:

```python
_TEAMS_REFERENCE_PATH = Path(__file__).resolve().parents[2] / "data" / "processed" / "teams_reference.csv"

@lru_cache(maxsize=1)
def _load_teams_reference() -> pd.DataFrame: ...

@lru_cache(maxsize=1)
def _fifa_ranking_lookup() -> dict[str, float]: ...

@lru_cache(maxsize=1)
def _confederation_lookup() -> dict[str, str]: ...

def get_fifa_ranking(team_name: str) -> float: ...      # NaN if unknown
def get_confederation(team_name: str) -> Optional[str]: ...  # None if unknown
```

Design goals satisfied:

- **No hardcoded team→rank mapping in Python.** The only thing hardcoded
  is the *file path*; every actual ranking/confederation value is read from
  the CSV at first use and cached in memory (`lru_cache(maxsize=1)`, so the
  file is parsed once per process, not once per lookup).
- **Swappable without code changes.** Updating rankings after the group
  stage, a new FIFA ranking cycle, etc. means overwriting
  `teams_reference.csv` (or repointing `_TEAMS_REFERENCE_PATH`) — no Python
  edit required. The one caveat: because the lookups are `lru_cache`'d,
  a running process won't pick up a CSV change until restarted (same
  caching tradeoff already accepted elsewhere in this codebase, e.g.
  `app/data/fifa_2026/__init__.py`'s `load_groups()`/`load_schedule()`).
  If hot-reload without a restart is ever needed, replace the `lru_cache`
  with the same TTL-cache pattern `loader.py` uses for the match
  DataFrame — not done here to avoid over-engineering a need that doesn't
  exist yet.
- **Path resolution is location-relative** (`Path(__file__).resolve()`),
  matching the existing convention in `app/data/fifa_2026/__init__.py`, so
  it works regardless of the process's current working directory.

## 3. Features added

All three are computed inside `build_feature_vector()`, alongside the
existing Elo block:

| Feature | Meaning | Missing-data behavior |
|---|---|---|
| `home_fifa_rank` | Home team's pre-tournament FIFA ranking (1 = best) | `NaN` if team not in the 48-team reference |
| `away_fifa_rank` | Away team's pre-tournament FIFA ranking | `NaN` if team not in the 48-team reference |
| `fifa_rank_diff` | `home_fifa_rank - away_fifa_rank` | `NaN` if either side is `NaN` |
| `same_confederation` | `1.0` if both teams share a confederation, `0.0` if not, else `NaN` | `NaN` if either team's confederation is unknown |

`NaN`, never a fabricated default. XGBoost (via `xgboost`'s native missing
value handling at training time, and via the existing
`.fillna(0.0)` calls in `predictor.py`/`train.py` at serve/train time) treats
missing values as informative rather than crashing — this is the same
missing-value convention already used throughout `feature_engineering.py`
(e.g. `get_confederation` returning `None` when unmatched, `compute_head_to_
head` returning population-average defaults only when there is *zero*
history, never a per-team fabricated number).

### Why complementary, not blended

Elo (`elo_difference`) and FIFA ranking (`fifa_rank_diff`) are **both**
retained as separate columns, deliberately not averaged/combined into one
number:

- They have different update dynamics: Elo updates after every single
  match this codebase has ingested (weighted by tournament importance);
  FIFA ranking is a periodic, committee-computed snapshot with its own
  (undisclosed in this dataset) methodology and update cadence.
- They can and do disagree (e.g. a team on a long unbeaten run might have a
  rapidly-rising Elo before the next official FIFA ranking cycle reflects
  it) — that *disagreement* is itself a potentially useful signal for a
  tree-based model (XGBoost) to split on, which a single blended score would
  destroy.
- Blending them would require an arbitrary weighting choice with no
  empirical basis yet (no trained model to validate it against). Keeping
  them separate lets the upcoming ML Engineering retrain/SHAP pass decide
  empirically how much weight each deserves, rather than this feature-
  engineering pass pre-deciding it via a hardcoded blend formula.

### Why confederation → a binary flag, not one-hot columns

`teams_reference.csv` has 6 confederations (UEFA 16, CAF 10, AFC 9,
CONCACAF 6, CONMEBOL 6, OFC 1 — real counts, not estimated). Two options
were considered:

- **One-hot per confederation** (6 new binary columns): adds 6 mostly-
  redundant columns whose cross-continental signal is already substantially
  captured by Elo/ranking differentials and by `tournament_weight`
  (World Cup qualifying paths differ by confederation, which already
  correlates with the historical opponent-strength features).
- **`same_confederation` flag** (chosen): a single, cheap, well-populated
  binary feature that captures the specific hypothesis worth testing —
  "same-confederation matchups behave differently" (e.g. more familiarity,
  different playing styles within a confederation) — without adding 5
  extra near-constant one-hot columns for the ML Engineering wave to prune.
  Raw confederation identity (which specific confederation each team is
  in) is left out because it's a nominal/unordered categorical that
  XGBoost handles poorly as a single numeric column without proper
  encoding, and one-hot felt like premature feature-space expansion for
  a signal `same_confederation` already targets more directly.

## 4. Why `teams_reference.csv`'s `elo_rating` column is NOT used directly

`teams_reference.csv` ships its own static `elo_rating` snapshot (mean
~1802, range 1510-2150 across the 48 teams). This is intentionally **not**
read into feature engineering as a second Elo signal:

- The dynamic Elo system (`ELO_SYSTEM.md`) already computes a full,
  continuously-updated Elo per team from `matches_historical.csv`/the
  `matches` table, going back to 2002 and incorporating every match
  ingested since (including in-progress 2026 results). That is a strictly
  richer, leakage-safe, per-as-of-date signal.
- The CSV's static snapshot is a single point-in-time value with no
  "as of this date" semantics — using it directly in `build_feature_vector`
  would mean every historical training row for a 2026 team gets the *same*
  future-dated Elo number regardless of match date, which is a leakage risk
  (a team's *current* 2026 Elo snapshot leaking backward into 2002-era
  training rows for that same team).
- If the two numbers ever need reconciling (e.g. to sanity-check the
  dynamic system's plausibility, or as a bootstrap prior for teams with
  thin history), that is a validation/calibration exercise for the ML
  Engineering wave, not a feature to add for the model to consume directly.

## 5. Coverage gap — non-2026 historical opponents

Checked directly (not asserted):

```
matches_historical.csv (2002-2022 rows): 73 unique teams total
teams_reference.csv (2026 field):        48 teams
Overlap:                                 48 / 48  (every 2026 team appears historically)
Missing from teams_reference.csv:        25 teams, e.g. Angola, Cameroon, Chile, China,
                                          Costa Rica, Denmark, Greece, Honduras, Iceland,
                                          Italy, Nigeria, North Korea, Peru, Poland,
                                          Republic of Ireland, Russia, Serbia,
                                          Serbia and Montenegro, Slovakia, Slovenia, ...
```

For any historical match involving one of these 25 teams, `home_fifa_rank`/
`away_fifa_rank`/`fifa_rank_diff`/`same_confederation` are `NaN` for that
side — never a fabricated rank or confederation. This is a real, documented
data gap (consistent with the Data Engineering wave's own framing in
`DATA_QUALITY_REPORT.md` and `KNOWN_ASSUMPTIONS.md` item (c)), not a bug in
this integration.

## 6. Sync with the database

The Database Engineering wave has already added `teams.fifa_ranking`
(reused pre-existing column) and `teams.elo_rating` (new column) via
`database/migrations/002_wc2026_upgrade.sql`, seeded from this same
`teams_reference.csv`. This feature-engineering integration reads the CSV
directly rather than the DB table, because:

- `feature_engineering.py` has no DB dependency today (it's pure
  pandas/numpy, tested with plain DataFrames — see
  `backend/tests/test_feature_engineering.py`), and adding one purely for a
  48-row static lookup would be a disproportionate coupling increase.
- The CSV and the DB column are seeded from the same source and are
  expected to agree; if they ever diverge (e.g. DB `fifa_ranking` gets
  updated in place after a new FIFA ranking cycle per the DB wave's
  `ranking_updated_at` trigger design, but the CSV isn't regenerated),
  **the CSV becomes stale** relative to the DB.

**Recommendation, not implemented here:** if live ranking updates (post-
launch) need to flow into predictions without a redeploy, point
`_TEAMS_REFERENCE_PATH`-equivalent logic at the `teams` table instead of
the CSV (a small async query alongside `load_matches_dataframe()` in
`loader.py`, cached with the same 6-hour TTL). Left as CSV-based for now
per the task's own suggested mechanism ("propose your own lookup
mechanism, e.g. a small JSON/CSV... note that the DB agent's `teams` table
... column should ultimately be kept in sync with this") — flagging this
explicitly rather than silently leaving two sources of truth undocumented.
