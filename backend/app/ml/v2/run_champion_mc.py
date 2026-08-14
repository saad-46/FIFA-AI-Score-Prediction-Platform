"""
Historical champion Monte Carlo + convergence check (Phase 11-12), plus
match-model-vs-simulator error attribution (Phase 10).

For each of the six historical tournaments: trains the model exactly as the
strict pre-tournament fold does (frozen at year-1), derives the REAL
knockout bracket from the actual match data (no fabricated seeding — see
historical.derive_bracket_from_data), and runs a Monte Carlo simulation
conditioned on the real Round-of-16 field to get a champion probability
distribution. Reports the rank/probability of the actual champion, top-3/
top-5 inclusion, and the champion Brier score.

Usage:
    backend/venv/Scripts/python.exe -m app.ml.v2.run_champion_mc
"""

from __future__ import annotations

import json
from pathlib import Path

from app.ml.v2.experiments import CLF_PARAMS, REG_PARAMS
from app.ml.v2.features import load_canonical
from app.ml.v2.historical import (HISTORICAL_YEARS, champion_monte_carlo,
                                  monte_carlo_convergence, run_tournament_fold)

ART = Path(__file__).resolve().parent / "artifacts"
BASELINE_GROUPS = ("strength", "form", "history", "context")

#: EXP-007's tuned hyperparameters — the current accepted best configuration
#: (see run_experiments.py / hyperparam_search.py). Champion MC should use
#: the same model that will actually be frozen, not the stale defaults.
TUNED_PARAMS = {"max_depth": 3, "learning_rate": 0.03328934350873081, "n_estimators": 200,
                "min_child_weight": 3, "subsample": 0.6950873836384747,
                "colsample_bytree": 0.860456436297428, "reg_alpha": 0.2586762826070334,
                "reg_lambda": 1.2456180155061534}
TUNED_CLF_PARAMS = dict(CLF_PARAMS, **TUNED_PARAMS)
TUNED_REG_PARAMS = dict(REG_PARAMS, **TUNED_PARAMS)


def main() -> None:
    matches, teams, stats = load_canonical()
    report: dict = {"per_tournament": {}}

    print("=" * 78)
    print("CHAMPION MONTE CARLO — 6 historical tournaments, real R16 field")
    print("=" * 78)

    top3 = top5 = n = 0
    briers = []
    for year in HISTORICAL_YEARS:
        fold = run_tournament_fold(matches, teams, stats, year, BASELINE_GROUPS,
                                   TUNED_CLF_PARAMS, TUNED_REG_PARAMS)
        oracle = fold["oracle"]
        result = champion_monte_carlo(matches, year, oracle, n_sims=20000)
        report["per_tournament"][year] = result

        if "error" in result:
            print(f"  {year}: {result['error']}")
            continue

        n += 1
        top3 += int(result["actual_champion_in_top3"])
        top5 += int(result["actual_champion_in_top5"])
        briers.append(result["brier_champion"])

        print(f"  {year}  actual champion: {result['actual_champion']:<14} "
              f"model rank={result['actual_champion_rank']}  "
              f"p={result['actual_champion_probability']:.4f}  "
              f"top3={result['actual_champion_in_top3']}  top5={result['actual_champion_in_top5']}  "
              f"brier={result['brier_champion']:.4f}")
        top_favs = ", ".join(f"{r['team']} {r['p']*100:.0f}%" for r in result["champion_probabilities"][:3])
        print(f"         model's top-3 favourites: {top_favs}")

    print()
    print(f"Actual champion in model's top-3 in {top3}/{n} tournaments "
         f"({top3/n*100:.0f}%)" if n else "no valid tournaments")
    print(f"Actual champion in model's top-5 in {top5}/{n} tournaments "
         f"({top5/n*100:.0f}%)" if n else "")
    print(f"Mean champion Brier score: {sum(briers)/len(briers):.4f}" if briers else "")

    report["summary"] = {
        "n_tournaments": n,
        "actual_champion_top3_rate": round(top3 / n, 4) if n else None,
        "actual_champion_top5_rate": round(top5 / n, 4) if n else None,
        "mean_champion_brier": round(sum(briers) / len(briers), 4) if briers else None,
    }

    # ---- convergence check (Phase 11) on two representative tournaments ----
    print()
    print("=" * 78)
    print("MONTE CARLO CONVERGENCE — 10k / 50k / 100k sims")
    print("=" * 78)
    report["convergence"] = {}
    for year in (2010, 2022):  # one mid-sample, one recent — representative, not exhaustive
        fold = run_tournament_fold(matches, teams, stats, year, BASELINE_GROUPS,
                                   TUNED_CLF_PARAMS, TUNED_REG_PARAMS)
        conv = monte_carlo_convergence(matches, year, fold["oracle"],
                                       sim_counts=(10_000, 50_000, 100_000))
        report["convergence"][year] = {k: v for k, v in conv.items() if k != "detail"}
        print(f"  {year}  top team stable across counts: "
             f"{list(conv['top_team_by_sim_count'].values())}  "
             f"max_drift(50k->100k)={conv['max_probability_drift_last_two_counts']:.4f}  "
             f"converged={conv['converged']}")

    (ART / "historical_champion_mc.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nreport -> {ART / 'historical_champion_mc.json'}")


if __name__ == "__main__":
    main()
