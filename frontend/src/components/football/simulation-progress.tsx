"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

const STAGES = [
  "Seeding groups…",
  "Simulating knockout rounds…",
  "Aggregating simulations…",
  "Finalizing probabilities…",
];

interface SimulationProgressProps {
  /** Rough expected duration in ms, used only to pace the stage-label
   * cycling — the backend doesn't stream real progress, so this is honest
   * pacing, not a fake percentage bar. */
  expectedDurationMs?: number;
  /** The n_simulations actually sent to the API, so the wait state reports the
   * run the user configured rather than a hardcoded figure. */
  simulations?: number;
}

/** The designed wait state for /tournament/simulate (about 1-12s depending
 * on the simulation count) —
 * replaces a generic spinner with staged, legible status text. */
export function SimulationProgress({ expectedDurationMs = 7000, simulations }: SimulationProgressProps) {
  const [stageIndex, setStageIndex] = useState(0);

  useEffect(() => {
    const interval = expectedDurationMs / STAGES.length;
    const timer = setInterval(() => {
      setStageIndex((i) => Math.min(i + 1, STAGES.length - 1));
    }, interval);
    return () => clearInterval(timer);
  }, [expectedDurationMs]);

  return (
    <Card>
      <CardContent className="flex flex-col items-center justify-center gap-4 py-12 text-center">
        <Loader2 className="h-6 w-6 animate-spin text-primary" aria-hidden="true" />
        <div className="space-y-1.5">
          {/* Names the endpoint's actual job; nothing is being "calibrated" here. */}
          <p className="eyebrow">Simulating the tournament</p>
          <p className="text-sm font-bold text-foreground" role="status" aria-live="polite">
            {STAGES[stageIndex]}
          </p>
          {/* Was hardcoded "100k" regardless of the selected count — a run of
              10,000 reported 100,000. Reports the real parameter, or stays
              silent rather than guessing. */}
          {simulations !== undefined && (
            <p className="mt-1 select-none text-xs text-fg-muted">
              Running {simulations.toLocaleString()} tournament simulations.
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
