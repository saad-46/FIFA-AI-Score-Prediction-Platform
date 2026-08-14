"""
Establishes the "Current V2" baseline row for the historical-optimization
comparison table (Phase 15) — the current E4_plus_context feature set and
CLF/REG hyperparameters, evaluated under the strict pre-tournament-freeze
regime (see historical.py's module docstring for why this differs from the
original ablation numbers).

Logged to the experiment registry as EXP-001 with category "baseline" so
every later experiment's delta is measured against a recorded, reproducible
reference rather than a number quoted from memory.

Usage:
    backend/venv/Scripts/python.exe -m app.ml.v2.run_baseline
"""

from __future__ import annotations

import json
from pathlib import Path

from app.ml.v2.experiments import CLF_PARAMS, REG_PARAMS
from app.ml.v2.historical import HISTORICAL_YEARS, composite_objective, run_historical_simulation
from app.ml.v2.registry import log_experiment

ART = Path(__file__).resolve().parent / "artifacts"
BASELINE_GROUPS = ("strength", "form", "history", "context")


def main() -> None:
    print(f"Running historical simulation for CURRENT V2 baseline "
          f"(groups={BASELINE_GROUPS}) across {HISTORICAL_YEARS}...")
    result = run_historical_simulation(BASELINE_GROUPS, CLF_PARAMS, REG_PARAMS)

    for y in HISTORICAL_YEARS:
        m = result["per_tournament"][y]["metrics"]
        p = result["per_tournament"][y]["progression"]
        print(f"  {y}  acc={m['accuracy']:.4f} ll={m['log_loss']:.4f} brier={m['brier_multiclass']:.4f} "
              f"ece={m['ece']:.4f} drawF1={m['draw_f1']:.4f} scoreMAE={m['home_goals_mae']:.3f}/"
              f"{m['away_goals_mae']:.3f}  progression={p['correct']}/{p['n']}")

    agg = result["aggregate"]
    print()
    print("AGGREGATE (mean across 6 tournaments):")
    for k, v in agg["mean"].items():
        print(f"  {k:<24} {v}  (std={agg['std'].get(k)})")
    print(f"  knockout_progression_accuracy: {agg['knockout_progression_accuracy']}")

    composite = agg["mean"]["composite_objective"]

    record = log_experiment(
        category="baseline",
        description="Current V2 (E4_plus_context: strength+form+history+context), "
                    "existing CLF/REG hyperparameters, evaluated under strict "
                    "pre-tournament freeze (freeze_after_year=year-1 per fold, "
                    "no in-tournament leakage).",
        change={"feature_groups": list(BASELINE_GROUPS), "clf_params": CLF_PARAMS,
                "reg_params": REG_PARAMS},
        training_range="1930 - (year-1) per fold",
        validation_range=f"{HISTORICAL_YEARS} (WC2026 excluded)",
        aggregate_metrics=agg["mean"],
        composite_objective=composite,
        baseline_composite_objective=composite,  # baseline is its own reference
        accepted=True,
        reason="Reference baseline — not a candidate change, always retained "
              "as the comparison point for every subsequent experiment.",
    )
    print(f"\nlogged as {record['id']}")

    # Save full ledger + report
    ledger_path = ART / "historical_baseline_ledger.csv"
    result["ledger"].to_csv(ledger_path, index=False)

    report = {
        "feature_groups": list(BASELINE_GROUPS), "years": HISTORICAL_YEARS,
        "per_tournament": {str(y): {"metrics": v["metrics"], "progression": v["progression"],
                                    "group_qualification": v["group_qualification"]}
                          for y, v in result["per_tournament"].items()},
        "aggregate": agg, "composite_objective": composite,
        "experiment_id": record["id"],
    }
    (ART / "historical_baseline_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"ledger -> {ledger_path}")
    print(f"report -> {ART / 'historical_baseline_report.json'}")


if __name__ == "__main__":
    main()
