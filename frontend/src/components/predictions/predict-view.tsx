"use client";

import { useState } from "react";
import { Brain } from "lucide-react";
import { PredictionForm } from "@/components/predictions/prediction-form";
import { PredictionResultCard } from "@/components/predictions/prediction-result";
import { ReasoningLoader } from "@/components/predictions/reasoning-loader";
import { EmptyState } from "@/components/ui/empty-state";
import { cn } from "@/lib/utils";
import { useUser } from "@/hooks/use-user";
import type { PredictionResult } from "@/types";

export function PredictView() {
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const { isAuthenticated } = useUser();

  // 12-column split rather than a 50/50 one: the parameter form is a fixed,
  // compact control and does not grow with the viewport, whereas the results
  // carry two charts, SHAP bars and H2H. Giving both halves equal width forced
  // every result section into one narrow column on desktop. Before a result
  // exists the form gets more room, so the empty state does not look stranded.
  const resultsShown = loading || result !== null;

  return (
    <div
      className={cn(
        "grid grid-cols-1 items-start gap-8",
        resultsShown ? "lg:grid-cols-12" : "lg:grid-cols-2"
      )}
    >
      <div className={cn(resultsShown && "lg:col-span-4 xl:col-span-3")}>
        <PredictionForm
          onResult={(res) => {
            setResult(res);
            setLoading(false);
          }}
          onStartPredict={() => {
            setResult(null);
            setLoading(true);
          }}
          onPredictError={() => {
            setLoading(false);
          }}
        />
      </div>
      <div className={cn(resultsShown ? "lg:col-span-8 xl:col-span-9" : "sticky top-24")}>
        {loading ? (
          <ReasoningLoader />
        ) : result ? (
          <PredictionResultCard result={result} isAuthenticated={isAuthenticated} />
        ) : (
          <div className="flex h-full min-h-[400px] flex-col items-center justify-center rounded-xl border border-dashed border-border/40 bg-zinc-950/20 backdrop-blur-sm p-8 text-center">
            <EmptyState
              icon={Brain}
              title="Simulation Output Panel"
              description='Configure the model parameters on the left pane and execute "Run Simulation" to retrieve prediction data.'
            />
          </div>
        )}
      </div>
    </div>
  );
}
