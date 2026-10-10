"use client";

import { useEffect, useRef, useState } from "react";
import { PredictionForm } from "@/components/predictions/prediction-form";
import { PredictionResultCard } from "@/components/predictions/prediction-result";
import { ReasoningLoader } from "@/components/predictions/reasoning-loader";
import { useUser } from "@/hooks/use-user";
import type { PredictionResult } from "@/types";

/**
 * Match predictor: the fixture on top, its prediction underneath.
 *
 * Stacked rather than side by side. The fixture is naturally wide (team, "v",
 * team) and so is the scoreboard that answers it; in the old two-column split
 * the form was squeezed into a quarter-width column the moment a result
 * appeared, truncating the very team names it was showing.
 */
export function PredictView() {
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const { isAuthenticated } = useUser();
  const outputRef = useRef<HTMLDivElement>(null);

  // Bring the output into view when a run starts, and move focus to it when
  // the result lands so keyboard and screen-reader users arrive at the answer
  // rather than being left on the submit button.
  useEffect(() => {
    if (!loading && !result) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    outputRef.current?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
    if (result) outputRef.current?.focus({ preventScroll: true });
  }, [loading, result]);

  return (
    <div className="space-y-8">
      <PredictionForm
        onResult={(res) => {
          setResult(res);
          setLoading(false);
        }}
        onStartPredict={() => {
          setResult(null);
          setLoading(true);
        }}
        onPredictError={() => setLoading(false)}
      />

      <div ref={outputRef} tabIndex={-1} className="scroll-mt-24 focus:outline-none">
        {loading ? (
          <ReasoningLoader />
        ) : result ? (
          <PredictionResultCard result={result} isAuthenticated={isAuthenticated} />
        ) : (
          <div className="rounded-lg border border-dashed border-border px-5 py-10 text-center">
            <p className="font-display text-xl font-semibold uppercase tracking-wide text-fg-muted">No prediction yet</p>
            <p className="mx-auto mt-1.5 max-w-md text-sm leading-relaxed text-fg-subtle">
              Choose two teams and a venue above. You will get the chance of each result, each side&apos;s
              expected goals, the ten most likely scorelines and what drove the numbers.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
