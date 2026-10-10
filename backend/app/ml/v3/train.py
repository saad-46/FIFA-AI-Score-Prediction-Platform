"""
Reproducible V3 workflow.  Run from ``backend/``:

    python -m app.ml.v3.train validate      # data contract report
    python -m app.ml.v3.train tune          # rating hyper-parameter search (dev folds)
    python -m app.ml.v3.train benchmark     # all candidates, selection, final 2026 test
    python -m app.ml.v3.train fit           # build the two model bundles + manifests
    python -m app.ml.v3.train forecast      # pre-tournament 2026 forecast artefact
    python -m app.ml.v3.train all           # everything above, in order

Training never runs inside the API. These commands write versioned artefacts to
``app/ml/v3/artifacts/``; the API only loads them.

Bundles
-------
    wc2026_pretournament   information cutoff 2026-06-11 (the eve of the opening
                           match). Used for the historical pre-tournament forecast.
    current                information cutoff = the day after the last match in
                           the corpus. Used for live fixture predictions.

``ACTIVE.json`` names the bundle the API serves and the one before it, which is
the rollback target (``python -m app.ml.v3.train rollback``).
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
import warnings
from dataclasses import replace
from pathlib import Path
from typing import Any

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")
warnings.filterwarnings("ignore")

import joblib
import numpy as np
import pandas as pd

from app.ml.v3 import PIPELINE_VERSION, backtest as bt
from app.ml.v3.benchmark import evaluate_fold, run_benchmark, select, tune_rating_config, _fit_fold
from app.ml.v3.data import corpus_fingerprint, load_matches, source_provenance
from app.ml.v3.features import FEATURE_NAMES, FEATURE_REGISTRY, SCHEMA_VERSION, build_training_frame
from app.ml.v3.models import encode_y
from app.ml.v3.pipeline import fit_on_split, fit_production
from app.ml.v3.ratings import EloConfig

ART = Path(__file__).resolve().parent / "artifacts"
SEED = 42


def _write(name: str, obj: Any) -> Path:
    ART.mkdir(exist_ok=True)
    p = ART / name
    p.write_text(json.dumps(obj, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    print(f"  wrote {p.relative_to(ART.parents[3])}")
    return p


def _read(name: str) -> Any:
    return json.loads((ART / name).read_text(encoding="utf-8"))


def _env() -> dict[str, str]:
    import sklearn, xgboost, scipy
    return {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__, "xgboost": xgboost.__version__, "scipy": scipy.__version__}


# ── commands ─────────────────────────────────────────────────────────────────

def cmd_validate() -> None:
    matches, rep = load_matches(return_report=True)
    out = {
        **rep.to_dict(),
        "date_range": [str(matches.date.min().date()), str(matches.date.max().date())],
        "teams": int(len(set(matches.team_a) | set(matches.team_b))),
        "tournaments": int(matches.tournament.nunique()),
        "by_tier": {int(k): int(v) for k, v in matches.tier.value_counts().sort_index().items()},
        "non_fifa_competition_rows": int((~matches.is_fifa_recognised_competition).sum()),
        "result_shares": {k: round(float(v), 4) for k, v in matches.result.value_counts(normalize=True).items()},
        "corpus_fingerprint": corpus_fingerprint(),
        "source": source_provenance(),
        "feature_registry": [f.__dict__ for f in FEATURE_REGISTRY],
    }
    _write("data_validation_report.json", out)
    print(f"  {out['rows_out']} matches, {out['teams']} teams, issues: {out['issues']}")


def cmd_tune() -> None:
    matches = load_matches()
    t0 = time.time()
    cfg, trials = tune_rating_config(matches)
    _write("rating_search.json", {"selected": cfg.to_dict(), "tuned_on_folds": ["2010-2013", "2014-2017", "2018-2021"],
                                  "trials": trials, "seconds": round(time.time() - t0, 1)})
    if cfg != EloConfig():
        print("  NOTE: search result differs from EloConfig defaults -- update ratings.EloConfig to adopt it.")


def cmd_benchmark() -> None:
    matches = load_matches()
    frame, _ = build_training_frame(matches)
    print("development folds")
    res = run_benchmark(frame)
    sel = select(res["dev_mean_log_loss"])
    print(f"  selected: {sel['selected']}")

    # ---- final test: 2026, scored once, with everything already decided ------
    print("final fold (2026) -- scored once")
    fold = bt.FINAL_FOLD
    fit = _fit_fold(frame, fold, xgb_params=res["xgb_params_selected"], seed=SEED)
    final = evaluate_fold(fit)
    cal_probs = final.pop("_cal_probs")
    test, y = fit["test"], fit["y_test"]

    train, val, _ = bt.split(frame, fold)
    fc = fit_on_split(train, val, res["xgb_params_selected"], SEED)
    p = fc.predict_proba(test)
    goals = fc.predict_goals(test)
    actual = (test["goals_a"].to_numpy(), test["goals_b"].to_numpy())
    wc = ((test["tournament"] == "FIFA World Cup")).to_numpy()
    selected_final = {
        "all_2026": bt.score(p, y, goals, actual),
        "world_cup_2026": bt.score(p[wc], y[wc], (goals[0][wc], goals[1][wc]), (actual[0][wc], actual[1][wc])),
        "class_report_all_2026": bt.class_report(p, y),
        "reliability": bt.reliability_table(p, y),
        "slices": bt.slices(test, p, y),
        "vs_prior": bt.bootstrap_diff(p, cal_probs["prior"], y),
        "vs_elo": bt.bootstrap_diff(p, cal_probs["elo_ordered_logit"], y),
        "world_cup_vs_prior": bt.bootstrap_diff(p[wc], cal_probs["prior"][wc], y[wc]),
        "world_cup_vs_elo": bt.bootstrap_diff(p[wc], cal_probs["elo_ordered_logit"][wc], y[wc]),
        "model_meta": fc.meta,
    }
    wc_table = {k: bt.score(v[wc], y[wc]) for k, v in cal_probs.items()}

    report = {
        "pipeline_version": PIPELINE_VERSION, "feature_schema": SCHEMA_VERSION, "features": list(FEATURE_NAMES),
        "corpus_fingerprint": corpus_fingerprint(), "environment": _env(), "seed": SEED,
        "protocol": {
            "train_start": bt.TRAIN_START,
            "folds": [f.__dict__ for f in bt.FOLDS],
            "note": "features are pre-match snapshots from one chronological walk; each fold fits on train, "
                    "early-stops on the first half of validation, calibrates on the second half, and is "
                    "scored on test. The 2026 fold played no part in any choice.",
        },
        "development": res, "selection": sel,
        "final_2026": {"candidates": final, "world_cup_2026_by_candidate": wc_table, "selected_model": selected_final},
    }
    _write("benchmark_report.json", report)
    _write_markdown(report)
    s = selected_final
    print(f"  selected on 2026: n={s['all_2026']['n']} log_loss={s['all_2026']['log_loss']} "
          f"acc={s['all_2026']['accuracy']} | WC2026 n={s['world_cup_2026']['n']} "
          f"log_loss={s['world_cup_2026']['log_loss']} acc={s['world_cup_2026']['accuracy']}")


def _write_markdown(rep: dict) -> None:
    L: list[str] = ["# V3 benchmark", "",
                    f"Corpus `{rep['corpus_fingerprint']}` · pipeline {rep['pipeline_version']} · seed {rep['seed']}", "",
                    "All figures are out-of-sample. Probabilities are temperature-scaled on a validation period "
                    "that precedes the test period. Lower is better for log loss, Brier and RPS.", ""]

    def table(title: str, rows: list[tuple[str, dict]]) -> None:
        L.extend([f"## {title}", "",
                  "| Model | n | Log loss | Brier | RPS | Accuracy | Draw recall | Goal MAE | ECE |",
                  "|---|---|---|---|---|---|---|---|---|"])
        for name, m in rows:
            L.append(f"| {name} | {m['n']} | {m['log_loss']:.4f} | {m['brier']:.4f} | {m['rps']:.4f} | "
                     f"{m['accuracy']:.3f} | {m['draw_recall']:.3f} | {m.get('goal_mae', '—')} | {m['ece']:.3f} |")
        L.append("")

    def rows_for(ev: dict) -> list[tuple[str, dict]]:
        out = []
        for k, v in ev["calibration"].items():
            m = dict(v["temperature"])
            if "goal_mae" in ev["models"][k]:
                m["goal_mae"] = ev["models"][k]["goal_mae"]
            out.append((k, m))
        out.extend((k, v) for k, v in ev["ensembles"].items())
        return out

    for ev in rep["development"]["dev_folds"]:
        table(f"Development fold {ev['fold']}", rows_for(ev))
    L.extend(["## Mean development log loss", "", "| Model | Mean log loss |", "|---|---|"])
    for k, v in sorted(rep["development"]["dev_mean_log_loss"].items(), key=lambda x: x[1]):
        L.append(f"| {k} | {v:.5f} |")
    sel = rep["selection"]
    L.extend(["", f"**Selected: `{sel['selected']}`** — {sel['rule']}. Within the tie margin "
              f"({sel['tie_margin']}): {', '.join(sel['within_tie_margin'])}.", "",
              "## Calibration method (mean development log loss, all non-baseline models)", "",
              "| Method | Mean log loss |", "|---|---|"])
    for k, v in sorted(rep["development"]["calibration_dev_mean_log_loss"].items(), key=lambda x: x[1]):
        L.append(f"| {k} | {v:.5f} |")
    L.append("")
    table("Final test — all 2026 matches (untouched until selection was complete)", rows_for(rep["final_2026"]["candidates"]))
    table("Final test — World Cup 2026 only", list(rep["final_2026"]["world_cup_2026_by_candidate"].items()))
    s = rep["final_2026"]["selected_model"]
    L.extend(["## Selected model on the final test", "",
              f"- All 2026: {json.dumps(s['all_2026'])}",
              f"- World Cup 2026: {json.dumps(s['world_cup_2026'])}",
              f"- Log-loss difference vs class prior (all 2026): {json.dumps(s['vs_prior'])}",
              f"- Log-loss difference vs Elo (all 2026): {json.dumps(s['vs_elo'])}",
              f"- vs class prior (World Cup): {json.dumps(s['world_cup_vs_prior'])}",
              f"- vs Elo (World Cup): {json.dumps(s['world_cup_vs_elo'])}", ""])
    (ART / "BENCHMARK_V3.md").write_text("\n".join(L), encoding="utf-8")
    print("  wrote artifacts/BENCHMARK_V3.md")


def _bundle(name: str, cutoff: pd.Timestamp, frame: pd.DataFrame, xgb_params: dict, extra: dict) -> None:
    fc = fit_production(frame, cutoff, xgb_params, SEED)
    path = ART / f"model_{name}.joblib"
    tmp = path.with_suffix(".tmp")
    joblib.dump(fc, tmp)
    os.replace(tmp, path)                      # atomic: a reader never sees a half-written bundle
    manifest = {
        "name": name, "pipeline_version": PIPELINE_VERSION, "feature_schema": SCHEMA_VERSION,
        "features": list(FEATURE_NAMES), "information_cutoff": str(cutoff.date()),
        "corpus_fingerprint": corpus_fingerprint(), "source": source_provenance(),
        "rating_config": EloConfig().to_dict(), "model": fc.meta, "environment": _env(),
        "artifact": path.name, "artifact_sha256": _sha(path),
        "created": pd.Timestamp.utcnow().isoformat(), **extra,
    }
    _write(f"manifest_{name}.json", manifest)


def _sha(path: Path) -> str:
    from app.ml.v3.data import file_sha256
    return file_sha256(path)


def cmd_fit() -> None:
    from app.ml.v3.wc2026 import FORECAST_CUTOFF
    rep = _read("benchmark_report.json")
    xgb_params = rep["development"]["xgb_params_selected"]
    sel = rep["selection"]["selected"]
    matches = load_matches()
    frame, _ = build_training_frame(matches)
    extra = {"selected_candidate": sel, "benchmark": "benchmark_report.json"}
    _bundle("wc2026_pretournament", FORECAST_CUTOFF, frame, xgb_params,
            {**extra, "purpose": "historical pre-tournament forecast of the 2026 World Cup"})
    current_cutoff = matches["date"].max() + pd.Timedelta(days=1)
    _bundle("current", current_cutoff, frame, xgb_params, {**extra, "purpose": "live fixture predictions"})
    active = {"active": "current", "previous": None, "updated": pd.Timestamp.utcnow().isoformat()}
    if (ART / "ACTIVE.json").exists():
        old = _read("ACTIVE.json")
        active["previous"] = old.get("active")
    _write("ACTIVE.json", active)


def cmd_forecast(n_sims: int = 50000) -> None:
    from app.ml.v3.inference import ForecastService
    from app.ml.v3.tournament import simulate
    from app.ml.v3.wc2026 import actual_results, build_format

    svc = ForecastService.load("wc2026_pretournament")
    fmt, w = build_format(svc.matches_all)
    t0 = time.time()
    res = simulate(fmt, svc.sampler(tier=5), n_sims=n_sims, seed=20260611)
    secs = time.time() - t0

    # What actually happened, for the comparison only -- never an input above.
    replay = simulate(fmt, svc.sampler(tier=5), n_sims=1, seed=0, fixed=actual_results(fmt, w), n_batches=1)
    order = ["group", "r32", "r16", "qf", "sf", "final", "winner"]
    for t, row in res["teams"].items():
        reached = [s for s in order if replay["teams"][t][s] == 1.0]
        row["actual_furthest_stage"] = reached[-1]
        row["elo_pre_tournament"] = round(svc.engine.elo[t], 1)
    ranked = sorted(res["teams"].items(), key=lambda kv: -kv[1]["winner"])
    out = {
        "title": "FIFA World Cup 2026 — pre-tournament forecast",
        "status": "historical: the tournament finished on 2026-07-19",
        "information_cutoff": svc.manifest["information_cutoff"],
        "model": svc.manifest["name"], "pipeline_version": PIPELINE_VERSION,
        "corpus_fingerprint": svc.manifest["corpus_fingerprint"],
        "n_simulations": n_sims, "seed": res["seed"], "seconds": round(secs, 1),
        "diagnostics": res["diagnostics"],
        "assumptions": [
            "match probabilities: Poisson/Dixon-Coles + XGBoost blend, temperature-scaled",
            "host nations play at home in their own country, per the official schedule; all other matches neutral",
            "knockout ties: 90 minutes, then extra time at one third of the 90-minute scoring rates, then penalties",
            "penalty shoot-outs: " + str(svc.forecaster.meta["shootout"].get("used")),
            "group ties beyond head-to-head and overall goal difference/goals are settled by random draw "
            "(fair-play points and FIFA ranking are not available)",
        ],
        "actual_champion": [t for t, r in replay["teams"].items() if r["winner"] == 1.0][0],
        "ranking": [t for t, _ in ranked],
        "teams": res["teams"],
    }
    _write("wc2026_pretournament_forecast.json", out)
    print(f"  {n_sims} simulations in {secs:.1f}s; champion-probability sum = "
          f"{res['diagnostics']['champion_probability_sum']:.4f}")
    for t, r in ranked[:10]:
        print(f"   {t:<14} win {r['winner']*100:5.1f}%  final {r['final']*100:5.1f}%  sf {r['sf']*100:5.1f}%  "
              f"(actual: {r['actual_furthest_stage']})")
    usa = res["teams"]["USA"]
    print(f"   USA: rank {[t for t, _ in ranked].index('USA') + 1} of 48, win {usa['winner']*100:.2f}% "
          f"(actual: {usa['actual_furthest_stage']})")


def cmd_rollback() -> None:
    a = _read("ACTIVE.json")
    if not a.get("previous"):
        print("  no previous bundle recorded; nothing to roll back to")
        return
    _write("ACTIVE.json", {"active": a["previous"], "previous": a["active"],
                           "updated": pd.Timestamp.utcnow().isoformat()})


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m app.ml.v3.train")
    ap.add_argument("command", choices=["validate", "tune", "benchmark", "fit", "forecast", "rollback", "all"])
    ap.add_argument("--sims", type=int, default=50000)
    args = ap.parse_args(argv)
    steps = {"validate": cmd_validate, "tune": cmd_tune, "benchmark": cmd_benchmark, "fit": cmd_fit,
             "forecast": lambda: cmd_forecast(args.sims), "rollback": cmd_rollback}
    for name in (["validate", "tune", "benchmark", "fit", "forecast"] if args.command == "all" else [args.command]):
        print(f"[{name}]")
        steps[name]()


if __name__ == "__main__":
    main()
