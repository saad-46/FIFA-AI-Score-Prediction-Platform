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
}

/** The designed wait state for /tournament/simulate's real 5-9s latency —
 * replaces a generic spinner with staged, legible status text. */
export function SimulationProgress({ expectedDurationMs = 7000 }: SimulationProgressProps) {
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
      <CardContent className="flex flex-col items-center justify-center gap-4 py-16 text-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" aria-hidden="true" />
        <div>
          <p className="font-medium text-foreground" role="status" aria-live="polite">
            {STAGES[stageIndex]}
          </p>
          <p className="text-xs text-fg-muted mt-1">
            Running thousands of simulated tournaments — this takes a few seconds.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
