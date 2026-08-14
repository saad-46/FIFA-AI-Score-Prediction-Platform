"""
Controlled feature experiments (Phase 6) + hyperparameter search (Phase 7).

Every experiment changes exactly ONE thing relative to the current accepted
best configuration, is evaluated by the identical historical walk-forward
(2002-2022 only, strict pre-tournament freeze), and is logged to the
registry with an explicit accept/reject decision — regardless of outcome.

ACCEPTANCE RULE (documented, applied uniformly): a change is accepted only if
it improves the composite objective (historical.composite_objective) by more
than 0.005 — roughly 7% of the baseline's own std across the 6 tournaments
(0.0761), so a change has to clear a real signal-vs-noise bar, not just get
lucky on one or two of the six folds. This threshold is fixed BEFORE running
any experiment in this file, so it cannot be tuned after the fact to justify
a particular result.

Usage:
    backend/venv/Scripts/python.exe -m app.ml.v2.run_experiments
"""

from __future__ import annotations

from copy import deepcopy

from app.ml.v2.experiments import CLF_PARAMS, REG_PARAMS
from app.ml.v2.historical import HISTORICAL_YEARS, run_historical_simulation
from app.ml.v2.registry import log_experiment

ACCEPT_THRESHOLD = 0.005
BASELINE_GROUPS = ("strength", "form", "history", "context")


def try_experiment(category: str, description: str, groups: tuple[str, ...],
                   change: dict, baseline_composite: float,
                   clf_params: dict = CLF_PARAMS, reg_params: dict = REG_PARAMS,
                   exclude_features: tuple[str, ...] = ()) -> dict:
    result = run_historical_simulation(groups, clf_params, reg_params,
                                       exclude_features=exclude_features)
    agg = result["aggregate"]["mean"]
    composite = agg["composite_objective"]
    accepted = (baseline_composite - composite) > ACCEPT_THRESHOLD
    record = log_experiment(
        category=category, description=description, change=change,
        training_range="1930 - (year-1) per fold",
        validation_range=f"{HISTORICAL_YEARS} (WC2026 excluded)",
        aggregate_metrics=agg, composite_objective=composite,
        baseline_composite_objective=baseline_composite,
        accepted=accepted,
        reason=(f"composite improved by {baseline_composite - composite:.5f} "
                f"(> {ACCEPT_THRESHOLD} threshold)" if accepted else
                f"composite change {baseline_composite - composite:+.5f} did not "
                f"clear the {ACCEPT_THRESHOLD} threshold — within noise"),
    )
    print(f"{record['id']}  {description}")
    print(f"    composite={composite:.5f}  (baseline={baseline_composite:.5f}, "
          f"delta={record['delta_vs_baseline']:+.5f})  -> "
          f"{'ACCEPTED' if accepted else 'rejected'}")
    return record


def main() -> None:
    from app.ml.v2.registry import list_experiments
    baseline_records = [e for e in list_experiments("baseline")]
    if not baseline_records:
        raise RuntimeError("Run `python -m app.ml.v2.run_baseline` first — no baseline "
                           "logged in the registry to compare against.")
    baseline_composite = baseline_records[-1]["composite_objective"]
    print(f"Baseline composite objective: {baseline_composite:.5f} ({baseline_records[-1]['id']})\n")

    accepted_groups: list[str] = []

    print("=" * 78)
    print("B/C/D — Candidate feature groups (one at a time on top of baseline)")
    print("=" * 78)

    candidates = [
        ("form_compact",
         "B: recency-weighted single-window form (last 5, linear weights) — "
         "tests whether E2's failure was too many noisy raw-average form "
         "features, not the concept of recent form."),
        ("elo_surprise_form",
         "C: opponent-adjusted form via Elo 'surprise' (actual score minus "
         "Elo-expected score, averaged over last 5/10) — form that already "
         "accounts for opponent strength, unlike raw win/loss form."),
        ("elo_trend",
         "C: Elo momentum (current Elo minus Elo from 5 matches ago) per side."),
    ]
    for group_name, desc in candidates:
        groups = BASELINE_GROUPS + (group_name,)
        record = try_experiment(
            category="feature", description=desc, groups=groups,
            change={"added_group": group_name, "feature_groups": list(groups)},
            baseline_composite=baseline_composite)
        if record["accepted"]:
            accepted_groups.append(group_name)

    print()
    print("=" * 78)
    print("D — FIFA-rank redundancy: drop absolute ranks, keep only the difference")
    print("=" * 78)
    rank_record = try_experiment(
        category="feature_redundancy",
        description="D: drop home_fifa_rank/away_fifa_rank (absolute ranks), keep "
                    "only fifa_rank_diff — tests whether the two absolute-rank "
                    "columns add anything beyond what their own difference already "
                    "gives a tree model, or are just redundant noise.",
        groups=BASELINE_GROUPS,
        change={"dropped_columns": ["home_fifa_rank", "away_fifa_rank"]},
        baseline_composite=baseline_composite,
        exclude_features=("home_fifa_rank", "away_fifa_rank"))
    if rank_record["accepted"]:
        print("    -> dropping absolute ranks is now part of the accepted config")

    if len(accepted_groups) > 1:
        print()
        print(f"Multiple candidates accepted individually ({accepted_groups}) — "
              f"testing them combined (features can interact/be redundant):")
        combo_groups = BASELINE_GROUPS + tuple(accepted_groups)
        try_experiment(
            category="feature_combo",
            description=f"Combined: {', '.join(accepted_groups)} together on top of baseline.",
            groups=combo_groups,
            change={"added_groups": accepted_groups, "feature_groups": list(combo_groups)},
            baseline_composite=baseline_composite)

    print()
    print(f"\nAccepted feature groups this pass: {accepted_groups or '(none)'}")
    print("See app/ml/v2/artifacts/experiment_registry.json for the full log.")


if __name__ == "__main__":
    main()
