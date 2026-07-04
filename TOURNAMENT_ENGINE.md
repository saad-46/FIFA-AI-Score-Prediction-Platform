# Tournament Engine

Monte Carlo simulation engine for World Cup-style tournaments, implemented in
`backend/app/ml/tournament_simulator.py` and exposed via
`backend/app/api/v1/endpoints/tournament.py`. Grounded in the current source
as of 2026-07-02.

## FIFA World Cup 2026 format

- **48 teams, 12 groups (A-L), 4 teams per group.**
- Group stage: round robin (3 pts win, 1 pt draw), all 6 matches per group
  simulated (`combinations(group_teams, 2)`).
- Qualification to Round of 32: **top 2 of each group (24 teams) + best 8
  third-placed teams** across all 12 groups, ranked by the same tiebreak
  metrics used within a group.
- Knockout: **Round of 32 → Round of 16 → Quarter-Finals → Semi-Finals →
  Third-Place Match + Final** — single elimination from R32 onward.
- The official schedule (`app/data/fifa_2026/schedule.json`) breaks down as
  72 group-stage + 16 R32 + 8 R16 + 4 QF + 2 SF + 1 third-place + 1 final =
  **104 matches total**.

## Tiebreaker rules

Within a group, and when ranking runners-up/third-placed teams across
groups, the same ordered tiebreak chain is applied (`sort_key` in
`_run_simulation_batch`):

1. Points
2. Goal difference
3. Goals for
4. Head-to-head points (sum vs. the other teams compared)
5. Head-to-head goal difference
6. Head-to-head goals for
7. Random (final tiebreak — matches FIFA's coin-toss/drawing-of-lots
   provision for genuinely unresolved ties)

## R32 bracket construction — Pot 1 / Pot 2

- **Pot 1**: the 12 group winners + the **best 4 of the 12 runners-up**,
  ranked by the tiebreak chain above.
- **Pot 2**: the remaining 8 runners-up + the best 8 third-placed teams.
- Pairing avoids same-group rematches: each Pot 1 team is paired with the
  first available Pot 2 team from a different group; if no such team remains
  (edge case with unusual qualification patterns), it falls back to the next
  unpaired Pot 2 team regardless of group, so the bracket always completes.

## Knockout mechanics

- Regulation score: independent Poisson draws from each team's predicted
  expected goals for that matchup (`np.random.poisson(xg)`).
- Draws in the group stage stand as draws (1 point each).
- Draws in knockout matches go to **extra time**: an additional Poisson draw
  from each team's xG scaled to 33% (`xg * 0.33`), added to the regulation
  score.
- Still level after extra time → **penalties**, resolved probabilistically
  by each team's model-predicted win probability
  (`win_prob1 / (win_prob1 + win_prob2)`), not a fresh coin flip — a team
  the model favors is more likely to win penalties too.
- Third-place match: the two semi-final losers play each other; result is
  simulated but not tracked further (informational stage flag only, no
  fourth-place output field).

## The bug that was fixed

**Symptom:** `POST /tournament/simulate` always returned `group: 1.0` for
every team (correct — group stage is always reached) but **every other
stage — `r32`, `r16`, `qf`, `sf`, `third_place`, `final`, `winner` — was
always `0.0`**, for every team, with no visible error in the API response.

**Root cause:** `_run_simulation_batch` initialized each team's per-batch
stats dict with a **lowercase** `"group"` key
(`batch_stats = {team: {"group": 0, "r32": 0, ...}}`), then later wrote to
it using the **capital-G** `batch_stats[t]["Group"]`. Python dicts raise
`KeyError` on that mismatched key rather than silently creating a new entry
— but the exception happened inside a `ProcessPoolExecutor` worker, where it
was caught by the batch's own exception handling, logged, and swallowed
rather than propagated. Every single batch across every worker failed this
way, every run, so the aggregation loop only ever incremented `"group"`
counts and the other seven stages stayed at their zero-initialized value
forever — with no error surfaced to the API caller or even to the logs at a
severity anyone would notice.

**Fix:**
1. Corrected the key mismatch so `batch_stats[t]["group"]` (lowercase,
   matching the dict's own initialization) is what gets incremented.
2. Added real failure-rate tracking: `simulate_tournament()` now counts
   `completed_simulations` vs. requested `n_simulations`, and if **more than
   25% of batches fail**, raises `TournamentSimulationError` instead of
   silently normalizing against whatever partial data survived. The API
   layer maps this to **HTTP 503** with a descriptive detail message. If
   *all* batches fail, the same error is raised immediately rather than
   returning an all-zero response.
3. Results are normalized against `completed_simulations` (not the
   originally requested `n_simulations`), so a tolerated partial failure
   (under the 25% threshold) doesn't silently understate every probability.

**Regression coverage:** `backend/tests/test_tournament.py` and
`test_simulator.py` now assert that winner probabilities across all 48 teams
sum to approximately 1.0 (previously they summed to 0.0) — this is the test
that would have caught the original bug.

## Pot-1 runner-up seeding fix

Separately, the "best 4 runners-up" selection used to be a hardcoded
`winners + runners_up[:4]` — i.e. it always took the runners-up from groups
A-D by list position, regardless of which runners-up actually had the best
records. Now `runners_up_ranked` is sorted using the exact same tiebreak
chain as group-internal ranking (points → GD → GF → H2H → random) before
taking the top 4, matching how FIFA's actual 2026 draw is specified to work.

## FIFA 2026 reference data

`app/data/fifa_2026/` — see `KNOWN_ASSUMPTIONS.md` for full provenance
details. Summary:

- `groups.json` — the 12 official groups, 4 teams each (48 total), 3-letter
  codes + full names.
- `schedule.json` — all 104 official fixtures (date, ET kickoff time, host
  city, stage, group for group-stage matches). Knockout participants not
  yet determined are placeholders (`W##`/`L##`) matching the wallchart's own
  notation.
- `venues.json` — the 16 host cities and their region groupings.

Loaded via `app/data/fifa_2026/__init__.py`'s `lru_cache`-wrapped accessors
(`load_groups`, `load_schedule`, `load_venues`, `get_groups_as_team_codes`,
`filter_schedule`) — read from disk relative to the module's own location,
so they work regardless of the process's working directory.

### New 2026-specific endpoints

- `GET /api/v1/tournament/2026/groups` — the 12 groups as structured data.
- `GET /api/v1/tournament/2026/schedule?stage=&venue_city=` — the 104
  fixtures, filterable by stage or host city.
- `POST /api/v1/tournament/simulate` gained a `use_fifa_2026_groups: bool`
  flag — when `true`, the simulator uses `get_groups_as_team_codes()`
  instead of requiring the caller to paste all 48 team names into the
  request body. `TournamentSimulationRequest` also gained a Pydantic v2
  `model_validator` enforcing exactly 48 teams and no duplicates when
  `use_fifa_2026_groups` is `false`.

## Performance characteristics

Measured by the Performance Engineer's audit pass against a realistic
45,000-match synthetic dataset through the real trained model bundle:

- **Tournament matchup precompute (48 teams, 1128 pairs): ~268s → ~13.3s
  (~20x).** Root cause of the original cost: one sequential
  `MatchPredictor.predict()` call per pair (1128 individual model
  round-trips + SHAP overhead). Fix: `MatchPredictor.predict_batch()`
  collapses this into a small number of vectorized batch calls — one
  scaling pass and one `predict()`/`predict_proba()` call per model for the
  *entire* batch — plus per-team stats memoization (`team_stats_cache` in
  `build_feature_vector`) so each team's own rolling stats aren't
  recomputed once per pair it appears in.
- **`ProcessPoolExecutor` pickling overhead** for shipping the matchup
  cache into worker processes was separately measured at roughly
  **1.5ms per submit** — negligible relative to per-batch simulation cost,
  so no restructuring (e.g. shared memory) was applied.
- **Memory**: simulator memory use is bounded regardless of `n_simulations`
  — each worker only accumulates aggregated per-team stage counts
  (`batch_stats`), never per-simulation history, so requesting 100,000
  simulations doesn't multiply memory use versus requesting 1,000.

These numbers describe the simulator itself; end-to-end `POST
/tournament/simulate` latency also includes the per-request predictor/
DataFrame initialization (cached at module level in `tournament.py` after
the first call) and the Poisson-sampling cost of the actual Monte Carlo
loop, which scales with `n_simulations`.

## Tournament Engine audit — 2026-07-03 (in-progress tournament + new data wave)

By 2026-07-03 the real World Cup is in progress: 89 real 2026 matches exist
in `backend/app/data/processed/matches_historical.csv` (Data Engineering
wave output), with the group stage and part of the Round of 32 already
played. This pass verified the prior audit's automatic-sourcing fix still
holds, and extended the simulator to actually use the real, in-progress
results rather than blindly re-simulating matches that have already
happened.

### 1. No manual group/schedule input — confirmed, nothing to remove

Re-verified `tournament_simulator.py` and `endpoints/tournament.py` end to
end: there is no hardcoded/default team or group list anywhere in either
file. The only two paths into `TournamentSimulator.simulate_tournament` are
`get_groups_as_team_codes()` (official FIFA 2026 data, used when
`use_fifa_2026_groups=true`, the common case) or explicit client-submitted
groups validated by `TournamentSimulationRequest`'s Pydantic model (which
422s if `groups` is missing/malformed/wrong-count — this is a legitimate
"simulate a hypothetical bracket" feature, not a fallback default). No
change was needed here.

### 2. Completed-vs-simulated match handling — implemented

Previously the simulator ran a blind Monte Carlo simulation of the *entire*
tournament on every call, even for matches that have already been played in
reality. Since the tournament is genuinely in progress, this was a real
correctness gap: it treated known facts (e.g. "Canada beat South Africa
1-0 in the Round of 32") as still-uncertain coin flips.

**What changed** (`tournament_simulator.py`):

- `_load_completed_2026_results()` reads
  `backend/app/data/processed/matches_historical.csv`, filters to
  `tournament_year == 2026 & status == "Completed"` (76 matches as of
  2026-07-03: 72 group-stage + 4 Round-of-32), and translates team names
  into FIFA codes via `teams_reference.csv`'s canonical_name → fifa_code
  map (`_load_name_to_code_map()`) — matches_historical.csv uses display
  names like "South Korea" / "Bosnia and Herzegovina", while the simulator
  works entirely in groups.json/schedule.json's fifa_codes throughout, so
  this translation step is required for the two to line up.
- `_simulate_match_static()` now takes an optional `real_results` lookup: if
  the requested matchup was already played, it returns the REAL score
  instead of drawing from the Poisson model. Matches still `"Scheduled"`
  (including the one still-undetermined Round-of-16 slot for Canada's
  opponent, recorded as `"Unknown"` in the source data) are never in this
  dict, so they always fall through to genuine Monte Carlo simulation —
  the simulator never fabricates a result for an unplayed match.
- **Knockout-draw subtlety (a real bug found and fixed during this pass):**
  a completed Round-of-32 match can have a level regulation score in the
  real data (e.g. Germany 1-1 Paraguay) — but a knockout match always has a
  real winner (extra time / penalties), and `matches_historical.csv` only
  records the regulation scoreline, not who actually won the shootout. The
  first implementation naively returned `"Draw"` as the "winner" for such a
  match, which then crashed downstream with `KeyError: 'Draw'` when the
  bracket logic tried to advance `"Draw"` as if it were a team code. Fixed:
  for a knockout match whose real recorded score is level, the REAL
  regulation goals are used as the *starting* score, but extra
  time/penalties are still genuinely simulated from there (since the real
  shootout winner isn't data we have) — so e.g. Germany vs Paraguay now
  correctly shows a probabilistic split between the two teams reaching the
  Round of 16, instead of crashing or fabricating a winner.
- **Round-of-32 bracket correction (a second real bug found and fixed):**
  the group stage is now fully complete in reality, so every simulation's
  standings should reproduce the same 12 winners / 12 runners-up / 8
  best-thirds as real life — but the simulator's own Pot1/Pot2 pairing
  heuristic (pair each Pot1 team with the first available different-group
  Pot2 team, in list order) does **not** reliably reproduce FIFA's actual
  seeded R32 pairings even when the qualified teams match exactly. This
  meant real R32 results only got consulted in the fraction of simulations
  where the heuristic pairing happened to coincide with reality (observed:
  South Africa, who really lost to Canada, was incorrectly shown reaching
  the Round of 16 in ~68% of simulations). Fixed by adding
  `_load_real_r32_bracket()`, which reads the actual Round-of-32 pairings
  straight from `schedule.json` (already resolved to real fifa_codes, not
  `W##`/`L##` placeholders, and independently verified against real group
  results by the Data Engineering wave). `_run_simulation_batch` now uses
  this real bracket directly whenever a simulation's qualified teams exactly
  match the real bracket's 32 teams, falling back to the heuristic pairing
  otherwise (e.g. custom/hypothetical groups). After this fix, South Africa
  (real, decided loss) shows `r16 = 0.0` deterministically, and Germany/
  Paraguay (real draw, undecided shootout) show a genuine probabilistic
  split summing to 1.0.
- `TournamentSimulator.__init__` gained `use_real_results: bool = True`.
  When enabled (the default), `self.real_results` and `self.real_r32_bracket`
  are loaded once and threaded through every simulation batch. The API layer
  (`POST /tournament/simulate`) exposes this as `use_real_results` on
  `TournamentSimulationRequest` (default `true`), and forces it off whenever
  `use_fifa_2026_groups` is `false` — custom/hypothetical team labels can
  never coincide with a real fixture, so there's nothing to look up in that
  case, and forcing it off avoids pointless lookup work.
- Regression coverage added to `backend/tests/test_tournament.py`: real
  group-stage draw substitution (order-independent), real knockout-draw
  handling (never returns `"Draw"` as a final winner, shows genuine
  variance), the full real-bracket-override integration path against the
  actual `groups.json`/`schedule.json`/`matches_historical.csv` data
  (asserting South Africa's real elimination is reproduced every time), and
  the `use_real_results` flag's on/off plumbing.

### 3. Team-strength ratings (`teams_reference.csv`) wired into the simulator

`teams_reference.csv` (48 rows: canonical_name, fifa_code, group,
confederation, fifa_ranking_pre_tournament, elo_rating) was previously
unconsumed anywhere in the backend. In scope for the tournament simulator
specifically: the **last-resort fallback** used when a matchup prediction
call itself raises (inside `_precompute_matchups`'s per-pair retry loop,
after the batched `predict_batch()` call has already failed for the whole
tournament). This used to be a flat, team-agnostic guess (1.0/1.0 xG,
33/33/34% probabilities) regardless of how mismatched the two teams
actually are — the exact "sparse-data fallback ignores team strength" gap
called out for this wave, most visible for first-time-qualified nations
(Curaçao, Jordan, Iraq, Uzbekistan, Cabo Verde, Congo DR, Haiti — 3-4
historical matches each, all from the 2026 tournament itself, per
DATA_QUALITY_REPORT.md).

`TournamentSimulator._elo_fallback_prediction()` now uses
`teams_reference.csv`'s `elo_rating` (loaded once via
`_load_team_elo_ratings()`, keyed by fifa_code — same name→code bridge as
`real_results`) and the same Elo expected-score formula the feature
pipeline itself uses (`_elo_expected` in
`app/ml/features/feature_engineering.py`, replicated locally rather than
imported, to avoid coupling the simulator to feature-engineering internals
beyond this narrow read) to turn the rating gap into a win-probability
estimate, splitting a neutral total-goals expectation proportionally. Falls
back to the previous flat neutral guess only if either team's code isn't
found in `teams_reference.csv`.

This is deliberately narrow: it does **not** touch
`feature_engineering.py`'s own `BASE_ELO = 1500.0` fallback (used inside
`compute_dynamic_elo`/`_latest_elo_for_team` for the *trained model's*
own Elo features when a team has no prior match in the DataFrame passed to
it) — that fallback governs the model's actual feature vector at both
training and inference time and is explicitly the Feature Engineering
wave's scope, not the tournament simulator's. The `_elo_fallback_prediction`
wired in here only ever fires when the model call itself errors out, i.e.
it's a defensive fallback for a fallback path, not a change to how the
trained model is normally consulted.
