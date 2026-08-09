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
    <Card className="border border-border/80 bg-zinc-950/20 shadow-xl backdrop-blur-sm">
      <CardContent className="flex flex-col items-center justify-center gap-5 py-14 text-center font-mono">
        <div className="relative flex items-center justify-center h-12 w-12 rounded border border-cyan-500/30 bg-cyan-950/20 shadow-lg shadow-cyan-500/10">
          <Loader2 className="h-6 w-6 animate-spin text-primary" aria-hidden="true" />
        </div>
        <div className="space-y-1.5">
          <p className="text-[10px] tracking-widest text-zinc-500 uppercase">CALIBRATING MONTE CARLO SEED</p>
          <p className="text-sm font-bold text-foreground" role="status" aria-live="polite">
            {STAGES[stageIndex]}
          </p>
          <p className="text-xs text-fg-muted mt-1 select-none">
            Executing 100k simulation trees in real-time context.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
