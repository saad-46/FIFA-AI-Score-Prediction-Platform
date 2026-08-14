"""
Experiment registry — an append-only log of every candidate change tried
during historical optimization (Phase 21).

Exists specifically to guard against the failure mode the task calls out:
selecting a model because it happened to win on one or two tournaments after
many attempts. Every experiment is recorded regardless of outcome, with the
full metric set and an explicit accept/reject decision and reason, so the
selection process is auditable after the fact rather than just asserted.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path(__file__).resolve().parent / "artifacts" / "experiment_registry.json"


def _load() -> list[dict]:
    if REGISTRY_PATH.exists():
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return []


def _save(entries: list[dict]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


def log_experiment(
    *,
    category: str,
    description: str,
    change: dict[str, Any],
    training_range: str,
    validation_range: str,
    aggregate_metrics: dict[str, Any],
    composite_objective: float,
    baseline_composite_objective: float,
    accepted: bool,
    reason: str,
) -> dict:
    """Append one experiment record. Returns the record with its assigned id."""
    entries = _load()
    exp_id = f"EXP-{len(entries) + 1:03d}"
    record = {
        "id": exp_id,
        "date": datetime.now().astimezone().isoformat(timespec="seconds"),
        "category": category,
        "description": description,
        "change": change,
        "training_range": training_range,
        "validation_range": validation_range,
        "aggregate_metrics": aggregate_metrics,
        "composite_objective": composite_objective,
        "baseline_composite_objective": baseline_composite_objective,
        "delta_vs_baseline": round(baseline_composite_objective - composite_objective, 5),
        "accepted": accepted,
        "reason": reason,
    }
    entries.append(record)
    _save(entries)
    return record


def list_experiments(category: str | None = None) -> list[dict]:
    entries = _load()
    if category:
        entries = [e for e in entries if e["category"] == category]
    return entries


def accepted_experiments() -> list[dict]:
    return [e for e in _load() if e["accepted"]]


def summary() -> dict:
    entries = _load()
    return {
        "total_experiments": len(entries),
        "accepted": sum(1 for e in entries if e["accepted"]),
        "rejected": sum(1 for e in entries if not e["accepted"]),
        "by_category": {
            cat: sum(1 for e in entries if e["category"] == cat)
            for cat in sorted({e["category"] for e in entries})
        },
    }


def reset() -> None:
    """Test-only: clear the registry."""
    _save([])
